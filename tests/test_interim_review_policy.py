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
