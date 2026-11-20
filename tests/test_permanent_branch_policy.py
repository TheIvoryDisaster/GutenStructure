import copy
import unittest
from unittest.mock import patch
from scripts.permanent_branch_policy import policies,validate_policy,synchronize,SAFETY,BETA,STABLE

class PermanentPolicyTests(unittest.TestCase):
    def test_beta_review_bypass_cannot_bypass_pr_ci(self):
        safety,beta,stable=policies(['Release readiness'])
        self.assertEqual(safety['bypass_actors'],[])
        self.assertEqual(safety['conditions']['ref_name']['include'],['refs/heads/beta','refs/heads/main','refs/heads/release'])
        self.assertEqual(beta['bypass_actors'],[{'actor_type':'Team','actor_id':20738063,'bypass_mode':'pull_request'}])
        self.assertEqual(beta['conditions']['ref_name']['include'],['refs/heads/beta'])
        self.assertEqual([r['type'] for r in beta['rules']],['pull_request'])
        self.assertEqual(stable['bypass_actors'],[])
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
            if path.startswith('orgs/'):return {'id':20738063}
            if path.endswith('/Husbandry'):return {'owner':{'id':357134506},'private':False,'default_branch':'beta'}
            if path.endswith('/actions/permissions'):return {}
            if '/teams?' in path:return [{'id':20738063,'permission':'push'}]
            if '/rulesets?' in path:return []
            if '/rulesets/' in path:return copy.deepcopy(store[int(path.rsplit('/',1)[1])])
            if '/branches?' in path:return []
            raise AssertionError(path)
        with patch('scripts.permanent_branch_policy.discover_repositories',return_value=[{'repository':repo,'checks':['Release readiness']} ]):
            result=synchronize(api,{'policy_version':4,'repositories':[]},True)
        self.assertEqual(result['excluded_repositories'],[])
        self.assertEqual(result['repositories'][0]['repository'],repo)
        self.assertEqual({b['name'] for _,b in writes if b and b.get('enforcement')=='active'}, {SAFETY,BETA,STABLE})
    def test_release_gate_accepts_permanent_husbandry_and_rejects_bypass(self):
        from scripts.release_gate import validate_rules
        r=policies(['CI'])[2]['rules'][0];r['ruleset_id']=1
        detail={'name':STABLE,'enforcement':'active','bypass_actors':[]}
        validate_rules([r],lambda _:detail,repository='Meitou-Modding-Ecosystem/Husbandry')
        detail['bypass_actors']=[{'actor_type':'Team','actor_id':20738063}]
        with self.assertRaises(RuntimeError):validate_rules([r],lambda _:detail,repository='Meitou-Modding-Ecosystem/Husbandry')
