import copy
import unittest
from unittest.mock import patch
from scripts.permanent_branch_policy import policies as build,validate_policy,synchronize,SAFETY,BETA,STABLE
from scripts.release_gate import release_bypass as bypass_for, release_team_id

RELEASE_TEAM_ID=31415926
def policies(checks):return build(checks,RELEASE_TEAM_ID)
def release_bypass():return bypass_for(RELEASE_TEAM_ID)

class PermanentPolicyTests(unittest.TestCase):
    def test_beta_review_bypass_cannot_bypass_pr_ci(self):
        safety,beta,stable=policies(['Release readiness'])
        self.assertEqual(safety['bypass_actors'],[])
        self.assertEqual(safety['conditions']['ref_name']['include'],['refs/heads/beta','refs/heads/main','refs/heads/release'])
        self.assertEqual(beta['bypass_actors'],[{'actor_type':'Team','actor_id':20738063,'bypass_mode':'pull_request'}])
        self.assertEqual(beta['conditions']['ref_name']['include'],['refs/heads/beta'])
        self.assertEqual([r['type'] for r in beta['rules']],['pull_request'])
        self.assertEqual(stable['bypass_actors'],[{'actor_type':'Team','actor_id':RELEASE_TEAM_ID,'bypass_mode':'pull_request'}])
        self.assertEqual(stable['conditions']['ref_name']['include'],['refs/heads/main','refs/heads/release'])
        self.assertFalse(any('refs/heads/master' in r['conditions']['ref_name']['include'] for r in (safety,beta,stable)))
    def test_existing_checks_preserved_without_pilot_or_duplicates(self):
        safety,_,_=policies(['build / build','build / build','Meitou owner authorization (pilot)'])
        self.assertEqual(safety['rules'][-1]['parameters']['required_status_checks'],[{'context':'build / build','integration_id':15368}])
    def test_readback_rejects_bypass_on_mandatory_ci(self):
        wanted=policies(['CI'])[0];bad=copy.deepcopy(wanted);bad['bypass_actors']=[{'actor_type':'Team','actor_id':20738063,'bypass_mode':'pull_request'}]
        with self.assertRaises(ValueError):validate_policy(bad,wanted)
    def test_husbandry_is_included_and_all_new_repos_get_ci(self):
        writes=[];store={};repo='Meitou-Modding-Ecosystem/Husbandry'
        def api(path,method='GET',body=None):
            if method!='GET':
                writes.append((path,copy.deepcopy(body)))
                if method=='POST':
                    n=100+len(store);store[n]=copy.deepcopy(body);return {'id':n}
                if method=='DELETE':store.pop(int(path.rsplit('/',1)[1]),None)
                return {}
            if '/members?' in path:return [{'login':'maintainer'}]
            if path.startswith('orgs/') and '/rulesets?' in path:return []
            if path.endswith('/teams/release-debugger'):return {'id':RELEASE_TEAM_ID,'slug':'release-debugger'}
            if path.startswith('orgs/'):return {'id':20738063}
            if path.endswith('/Husbandry'):return {'owner':{'id':357134506},'private':False,'default_branch':'beta'}
            if path.endswith('/actions/permissions'):return {}
            if '/teams?' in path:return [{'id':20738063,'permission':'push'}]   # the release team is not assigned yet
            if '/rulesets?' in path:return []
            if '/rulesets/' in path:return copy.deepcopy(store[int(path.rsplit('/',1)[1])])
            if '/branches?' in path:return []
            raise AssertionError(path)
        with patch('scripts.permanent_branch_policy.discover_repositories',return_value=[{'repository':repo,'checks':['Release readiness']} ]):
            result=synchronize(api,{'policy_version':5,'release_bypass_team':'release-debugger','repositories':[]},True)
        self.assertEqual(result['excluded_repositories'],[])
        self.assertIn(('orgs/Meitou-Modding-Ecosystem/teams/release-debugger/repos/'+repo,{'permission':'push'}),writes)
        self.assertNotIn(('orgs/Meitou-Modding-Ecosystem/teams/super-maintainers/repos/'+repo,{'permission':'push'}),writes)
        stable=next(b for _,b in writes if b and b.get('name')==STABLE)
        self.assertEqual(stable['bypass_actors'],[release_bypass()])
        self.assertEqual(result['repositories'][0]['repository'],repo)
        self.assertEqual({b['name'] for _,b in writes if b and b.get('enforcement')=='active'}, {SAFETY,BETA,STABLE})
    def test_release_gate_accepts_permanent_husbandry_and_rejects_bypass(self):
        from scripts.release_gate import validate_rules
        r=policies(['CI'])[2]['rules'][0];r['ruleset_id']=1
        detail={'name':STABLE,'enforcement':'active','bypass_actors':[]}
        validate_rules([r],lambda _:detail,repository='Meitou-Modding-Ecosystem/Husbandry')
        detail['bypass_actors']=[{'actor_type':'Team','actor_id':20738063}]
        with self.assertRaises(RuntimeError):validate_rules([r],lambda _:detail,repository='Meitou-Modding-Ecosystem/Husbandry')
    def test_release_gate_accepts_only_the_release_teams_pr_bypass(self):
        from scripts.release_gate import validate_rules
        r=policies(['CI'])[2]['rules'][0];r['ruleset_id']=1
        repo='Meitou-Modding-Ecosystem/RivalryCore'
        detail={'name':STABLE,'enforcement':'active','bypass_actors':[release_bypass()]}
        validate_rules([r],lambda _:detail,repository=repo,release_team=RELEASE_TEAM_ID)
        for bad in ([dict(release_bypass(),bypass_mode='always')],                       # bypasses PRs too
                    [release_bypass(),{'actor_type':'Team','actor_id':20738063,'bypass_mode':'pull_request'}],
                    [{'actor_type':'OrganizationAdmin','actor_id':1,'bypass_mode':'pull_request'}]):
            detail['bypass_actors']=bad
            with self.assertRaises(RuntimeError):validate_rules([r],lambda _:detail,repository=repo,release_team=RELEASE_TEAM_ID)
        detail['bypass_actors']=[release_bypass()]
        with self.assertRaises(RuntimeError):validate_rules([r],lambda _:detail,repository=repo)   # the team's ID could not be read
        detail.update(bypass_actors=[release_bypass()],current_user_can_bypass='pull_requests_only')   # the gate's own token
        with self.assertRaises(RuntimeError):validate_rules([r],lambda _:detail,repository=repo,release_team=RELEASE_TEAM_ID)
        other={'name':'Some other ruleset','enforcement':'active','bypass_actors':[release_bypass()]}
        with self.assertRaises(RuntimeError):validate_rules([r],lambda _:other,repository=repo,release_team=RELEASE_TEAM_ID)
    def test_release_team_is_found_by_slug_or_not_at_all(self):
        self.assertEqual(release_team_id(lambda _:{'id':7,'slug':'release-debugger'}),7)
        self.assertIsNone(release_team_id(lambda _:{'id':7,'slug':'renamed'}))
        def denied(_):raise RuntimeError('HTTP 403')
        self.assertIsNone(release_team_id(denied))
    def test_reconciliation_refuses_a_release_team_that_is_super_maintainers(self):
        def api(path,method='GET',body=None):
            if '/members?' in path:return [{'login':'maintainer'}]
            if path.endswith('/teams/release-debugger'):return {'id':20738063,'slug':'release-debugger'}
            return {'id':20738063}
        with self.assertRaises(ValueError):synchronize(api,{'policy_version':5,'release_bypass_team':'release-debugger','repositories':[]})
