import hashlib
import hmac
import json
import unittest
from unittest.mock import patch
from scripts.owner_check_service import verify_webhook, evaluate_pr, CHECK
from scripts.custom_owner_policy import policies

class OwnerServiceTests(unittest.TestCase):
    def test_signed_webhook_only(self):
        body = b'{"installation":{"id":1}}'
        signature = 'sha256=' + hmac.new(b'secret', body, hashlib.sha256).hexdigest()
        self.assertEqual(verify_webhook(body, signature, 'secret')['installation']['id'], 1)
        for invalid in ('', 'sha256=bad'):
            with self.assertRaises(ValueError): verify_webhook(body, invalid, 'secret')
    def test_missing_secret_fails(self):
        with self.assertRaises(ValueError): verify_webhook(b'{}', '', '')
    def test_policy_requires_dedicated_app_and_preserves_ci(self):
        result = policies(['build / build'], 123)
        for rule in result:
            self.assertFalse(rule['bypass_actors'])
            checks = rule['rules'][-1]['parameters']['required_status_checks']
            self.assertIn({'context':CHECK,'integration_id':123}, checks)
            self.assertIn({'context':'build / build','integration_id':15368}, checks)
        self.assertEqual(result[1]['rules'][2]['parameters']['required_approving_review_count'], 1)
        self.assertFalse(result[1]['rules'][2]['parameters']['require_code_owner_review'])
        for value in (None, 0, True, 15368):
            with self.assertRaises(ValueError): policies([], value)
    def api(self):
        writes = []
        prs = [{'number': n, 'state':'open', 'head':{'sha':'a'*40},
                'base':{'ref':branch,'sha':'b'*40}} for n,branch in [(1,'beta'),(2,'release')]]
        def api(path, method='GET', data=None):
            if method != 'GET':
                writes.append((method, data)); return {'id':42}
            if path.endswith('/RivalryCore'): return {'owner':{'id':357134506},'private':False}
            if '/pulls?state=open' in path: return prs
            return prs[int(path.rsplit('/',1)[1])-1]
        return api, writes
    @patch('scripts.owner_check_service.preview')
    def test_beta_success_cannot_override_release_failure_at_same_head(self, preview):
        preview.side_effect = lambda repo,n,api: {'pr':n,'base':'b'*40,'policy_passed':n==1,'reasons':[] if n==1 else ['Needs independent review']}
        api,writes = self.api()
        self.assertFalse(evaluate_pr(api,'Meitou-Modding-Ecosystem/RivalryCore',1))
        self.assertEqual(preview.call_count,2)
        self.assertEqual(writes[-1][1]['conclusion'],'failure')
    @patch('scripts.owner_check_service.preview', side_effect=RuntimeError('sensitive API body'))
    def test_api_error_posts_failure_without_leaking_exception(self, preview):
        api,writes = self.api()
        self.assertFalse(evaluate_pr(api,'Meitou-Modding-Ecosystem/RivalryCore',1))
        self.assertNotIn('sensitive', json.dumps(writes))

class HistoryOnlyTests(unittest.TestCase):
    def test_empty_beta_diff_needs_no_path_review(self):
        from scripts.owner_approval import evaluate
        self.assertTrue(evaluate('alice','head','beta',[],'* @alice',[],{'@alice':{'alice'}})[0])
    def test_empty_release_diff_still_needs_independent_review(self):
        from scripts.owner_approval import evaluate
        self.assertFalse(evaluate('alice','head','release',[],'* @alice',[],{'@alice':{'alice'}})[0])

class ProbeTests(unittest.TestCase):
    def test_probe_reads_only_and_hides_private_repo_names(self):
        from scripts.owner_app_probe import probe
        def api(path):
            return {'repositories': [
                {'id':1,'full_name':'Meitou-Modding-Ecosystem/Public','owner':{'id':357134506},'private':False},
                {'id':2,'full_name':'Meitou-Modding-Ecosystem/Secret','owner':{'id':357134506},'private':True}]}
        result = probe(api,5828227)
        self.assertEqual(result['checks_written'],0)
        self.assertEqual(result['private_repositories_skipped'],1)
        self.assertNotIn('Secret',json.dumps(result))
