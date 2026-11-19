import unittest
from unittest.mock import patch
from scripts.husbandry_owner_pilot import run, REPO_ID

class HusbandryPilotTests(unittest.TestCase):
    def test_identity_mismatch_rejected_before_check_write(self):
        with self.assertRaises(ValueError): run(lambda path: {'id':0})
    @patch('scripts.husbandry_owner_pilot.service.evaluate_pr')
    def test_only_protected_prs_in_verified_husbandry_are_evaluated(self, evaluate):
        evaluate.return_value = True
        def api(path):
            if path.endswith('/Husbandry'):
                return {'id':REPO_ID,'owner':{'id':357134506},'private':False}
            return [{'number':1,'base':{'ref':'beta'}},{'number':2,'base':{'ref':'feature'}}]
        with patch('scripts.husbandry_owner_pilot.service.CHECK'):
            result = run(api)
        self.assertFalse(result['enforced'])
        self.assertEqual(result['rules_changed'],0)
        self.assertEqual(result['results'],[{'pr':1,'passed':True}])
        evaluate.assert_called_once()
