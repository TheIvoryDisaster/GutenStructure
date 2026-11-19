import unittest
from scripts.interim_review_policy import review,validate_native,capability_probe
class InterimTests(unittest.TestCase):
    def test_single_team_approval_no_codeowner_dependency(self):
        rule=review();p=rule['parameters']
        self.assertEqual(p['required_approving_review_count'],1)
        self.assertFalse(p['require_code_owner_review'])
        self.assertFalse(p['require_last_push_approval'])
        self.assertEqual(p['required_reviewers'][0]['reviewer']['id'],20738063)
    def test_ignored_team_field_is_rejected(self):
        rule=review();del rule['parameters']['required_reviewers']
        with self.assertRaises(ValueError):validate_native({'rules':[rule]})
    def test_probe_is_disabled_and_removed_on_rejection(self):
        calls=[]
        def api(path,method='GET',body=None):
            calls.append((method,body))
            if method=='POST':return {'id':42}
            if method=='GET':return {'rules':[]}
        with self.assertRaises(ValueError):capability_probe(api,'Meitou-Modding-Ecosystem/Example')
        self.assertEqual(calls[0][1]['enforcement'],'disabled')
        self.assertEqual(calls[-1][0],'DELETE')

    def test_gate_accepts_exact_interim_team_rule_except_husbandry(self):
        from scripts.release_gate import validate_rules
        rule=review();rule['ruleset_id']=1
        detail=lambda _: {'name':'Interim super-maintainer approval','enforcement':'active','bypass_actors':[]}
        validate_rules([rule],detail,repository='Meitou-Modding-Ecosystem/RivalryCore')
        with self.assertRaises(RuntimeError):validate_rules([rule],detail,repository='Meitou-Modding-Ecosystem/Husbandry')
        rule['parameters']['required_reviewers'][0]['reviewer']['id']=999
        with self.assertRaises(RuntimeError):validate_rules([rule],detail,repository='Meitou-Modding-Ecosystem/RivalryCore')

    def test_husbandry_is_excluded_from_all_mutations_and_old_reviews_removed(self):
        from unittest.mock import patch
        from scripts.interim_review_policy import synchronize,PILOT
        import copy
        repo='Meitou-Modding-Ecosystem/RivalryCore'
        writes=[];stored={}
        old={'id':1,'name':'Stable branch protection','target':'branch','enforcement':'active','bypass_actors':[],
             'conditions':{'ref_name':{'include':['refs/heads/release'],'exclude':[]}},
             'rules':[{'type':'pull_request','parameters':{'required_approving_review_count':2}},
                      {'type':'required_status_checks','parameters':{'strict_required_status_checks_policy':True,
                       'required_status_checks':[{'context':'build / build','integration_id':15368}]}}]}
        def api(path,method='GET',body=None):
            if PILOT in path:raise AssertionError('Pilot must not be read or mutated')
            if method!='GET':
                writes.append((method,path,copy.deepcopy(body)))
                if method=='POST':stored[50+len(stored)]=copy.deepcopy(body);return {'id':max(stored)}
                if method=='DELETE':stored.pop(int(path.rsplit('/',1)[1]),None)
                return {}
            if path.startswith('orgs/') and '/members?' in path:return [{'login':'maintainer'}]
            if path.startswith('orgs/'):return {'id':20738063}
            if path.endswith('/RivalryCore'):return {'owner':{'id':357134506},'private':False,'default_branch':'beta'}
            if path.endswith('/actions/permissions'):return {}
            if '/teams?' in path:return [{'id':20738063,'permission':'push'}]
            if '/rulesets?' in path:return [{'id':1,'name':old['name'],'source_type':'Repository'}]
            if '/rulesets/' in path:
                number=int(path.rsplit('/',1)[1]);return copy.deepcopy(old if number==1 else stored[number])
            if '/branches?' in path:return []
            raise AssertionError(path)
        with patch('scripts.interim_review_policy.discover_repositories',return_value=[{'repository':repo},{'repository':PILOT}]):
            result=synchronize(api,{'policy_version':3,'repositories':[]},True)
        self.assertEqual(len(result['repositories']),1)
        self.assertFalse(any(PILOT in p for _,p,_ in writes))
        replacements=[b for m,p,b in writes if m=='PUT' and p.endswith('/rulesets/1')]
        self.assertFalse(any(r['type']=='pull_request' for r in replacements[0]['rules']))
        self.assertFalse(replacements[0]['rules'][0]['parameters']['strict_required_status_checks_policy'])
