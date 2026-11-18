import base64
import copy
import unittest
from scripts.branch_policy import policies, organization_templates, legacy_replacement, synchronize
from scripts.apply_release_policy import GitHubFailure


class BranchTierTests(unittest.TestCase):
    def test_cli_entrypoint_uses_the_same_api_error_type(self):
        import runpy
        scope=runpy.run_path('scripts/apply_release_policy.py',run_name='policy_cli_boundary_test')
        self.assertIs(scope['GitHubFailure'],GitHubFailure)

    def test_only_main_beta_allow_selected_team_review_bypass(self):
        safety,owner,release,beta=policies(['build'],123)
        self.assertEqual(safety['bypass_actors'],[])
        self.assertEqual(owner['bypass_actors'],[{'actor_type':'Team','actor_id':123,'bypass_mode':'pull_request'}])
        self.assertEqual(owner['conditions']['ref_name']['include'],['refs/heads/main'])
        self.assertEqual(beta['conditions']['ref_name']['include'],['refs/heads/beta'])
        self.assertEqual(beta['bypass_actors'],[{'actor_type':'Team','actor_id':123,'bypass_mode':'pull_request'},
                                                {'actor_type':'Integration','actor_id':15368,'bypass_mode':'pull_request'}])
        self.assertEqual(safety['conditions']['ref_name']['include'],['refs/heads/beta','refs/heads/main'])
        self.assertEqual(release['conditions']['ref_name']['include'],['refs/heads/release'])
        self.assertEqual(release['bypass_actors'],[])
        params=next(r for r in release['rules'] if r['type']=='pull_request')['parameters']
        self.assertEqual(params['required_approving_review_count'],2)
        self.assertTrue(params['require_code_owner_review'])
        self.assertTrue(any(r['type']=='required_status_checks' for r in safety['rules']))
        self.assertFalse(any(r['type']=='required_status_checks' for r in owner['rules']))
        self.assertFalse(any('refs/heads/fork' in p['conditions']['ref_name']['include'] for p in (safety,owner,release,beta)))

    def test_org_templates_cover_new_repos_and_never_release_bypass(self):
        templates=organization_templates(123)
        for template in templates:
            self.assertEqual(template['conditions']['repository_name']['include'],['~ALL'])
            self.assertFalse(any(r['type']=='required_status_checks' for r in template['rules']))
        self.assertEqual(templates[2]['bypass_actors'],[])

    def test_legacy_review_overlap_removed_without_dropping_scanning(self):
        legacy=copy.deepcopy(policies(['build'],123)[0])
        legacy['conditions']['ref_name']['include']=['~DEFAULT_BRANCH']
        legacy['rules'].append({'type':'code_scanning','parameters':{'example':True}})
        converted=legacy_replacement(legacy,'beta')
        self.assertEqual(converted['conditions']['ref_name']['include'],['refs/heads/beta'])
        self.assertFalse(any(r['type']=='pull_request' for r in converted['rules']))
        self.assertTrue(any(r['type']=='code_scanning' for r in converted['rules']))
        legacy['conditions']['ref_name']['include']=['~DEFAULT_BRANCH','refs/heads/beta']
        converted=legacy_replacement(legacy,'main')
        self.assertEqual(converted['conditions']['ref_name']['include'],['refs/heads/main','refs/heads/beta'])
        legacy['conditions']['ref_name']['include']=['refs/heads/fork']
        with self.assertRaises(ValueError): legacy_replacement(legacy,'beta')

    def fake(self, team_access=True):
        writes=[]
        def api(path,method='GET',body=None):
            if method!='GET':
                writes.append((path,method,body));return {'id':10}
            if path=='orgs/Meitou-Modding-Ecosystem':return {'id':357134506}
            if '/teams' in path:
                if not team_access:raise GitHubFailure(403)
                return {'id':123,'slug':'super-maintainers'}
            if path.startswith('orgs/') and '/rulesets' in path:raise GitHubFailure(403)
            if '/repos?' in path:return [{'full_name':'Meitou-Modding-Ecosystem/NewMod','default_branch':'main','owner':{'id':357134506},'private':False}]
            if path.endswith('/actions/permissions'):return {'enabled':True}
            if '/branches/' in path and path.endswith('/protection'):raise GitHubFailure(404)
            if '/branches/' in path:return {'commit':{'sha':'test'}}
            if '/branches?' in path:return [{'name':'main','protected':False}]
            if '/contents/' in path:return {'content':base64.b64encode(b'* @Meitou-Modding-Ecosystem/super-maintainers').decode()}
            if '/codeowners/' in path:return {'errors':[]}
            if '/rulesets?' in path:return []
            if path=='repos/Meitou-Modding-Ecosystem/NewMod':return {'owner':{'id':357134506},'private':False,'default_branch':'main'}
            raise AssertionError(path)
        return api,writes

    def test_preview_is_readonly_and_apply_uses_four_separate_rules(self):
        plan={'branch':'release','repositories':[],'policy_version':2,'codeowner_self_merge_team':'super-maintainers'}
        api,writes=self.fake()
        result=synchronize(api,plan)
        self.assertEqual(writes,[])
        self.assertEqual(result['team']['id'],123)
        synchronize(api,plan,apply=True)
        self.assertEqual(len(writes),4)
        self.assertEqual(writes[2][2]['bypass_actors'],[])

    def test_unreadable_team_blocks_all_mutations(self):
        api,writes=self.fake(team_access=False)
        with self.assertRaises(ValueError):
            synchronize(api,{'branch':'release','repositories':[],'policy_version':2,'codeowner_self_merge_team':'super-maintainers'},apply=True)
        self.assertEqual(writes,[])


class AdministrationPreflightTests(unittest.TestCase):
    def test_missing_new_repository_administration_blocks_all_writes(self):
        api,writes=BranchTierTests().fake()
        def denied(path,method='GET',body=None):
            if path.endswith('/actions/permissions'): raise GitHubFailure(403)
            return api(path,method=method,body=body)
        with self.assertRaises(GitHubFailure):
            synchronize(denied,{'branch':'release','repositories':[],'policy_version':2,'codeowner_self_merge_team':'super-maintainers'},apply=True)
        self.assertEqual(writes,[])
