import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.author_publish import DownloadRedirects, fetch_payload, validate_context, validate_inputs, verify_source

REPO = 'Meitou-Modding-Ecosystem/RivalryCore'
SHA = 'a' * 40
DIGEST = 'b' * 64


class AuthorPublishTests(unittest.TestCase):
    def context(self):
        return dict(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REPOSITORY_OWNER='Author',
                    GITHUB_ACTOR='Author', GITHUB_TRIGGERING_ACTOR='Author', GITHUB_REPOSITORY_OWNER_ID='123', GITHUB_ACTOR_ID='123',
                    OWNER_TYPE='User', GITHUB_REF='refs/heads/main', DEFAULT_BRANCH='main')

    def test_only_owner_manual_default_branch_runs_are_accepted(self):
        validate_context(self.context())
        for key, value in [('GITHUB_EVENT_NAME','pull_request'), ('GITHUB_ACTOR','Other'),
                           ('GITHUB_ACTOR_ID','999'), ('OWNER_TYPE','Organization'),
                           ('GITHUB_REF','refs/heads/test'), ('GITHUB_TRIGGERING_ACTOR','Other')]:
            context = self.context()
            context[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_context(context)

    def test_exact_inputs_and_existing_destination_ids_required(self):
        args = [REPO, 'v1.0', SHA, '42', DIGEST, '1.0', '100']
        validate_inputs(*args)
        opaque = args.copy()
        opaque[6] = 'd6eb20d0-a049-4b42-8023-a03b8b312a69'
        validate_inputs(*opaque)
        for index, value in [(0,'Other/RivalryCore'),(1,'../tag'),(2,'main'),(3,'0'),(4,'bad'),(5,'$(id)'),(6,'0')]:
            bad = args.copy()
            bad[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_inputs(*bad)

    def api(self, path):
        base = f'repos/{REPO}'
        values = {
            base: {'private':False, 'owner':{'id':357134506}},
            base + '/releases/tags/v1.0': {'id':7,'tag_name':'v1.0','draft':False,'prerelease':False},
            base + '/git/ref/tags/v1.0': {'object':{'type':'tag','sha':'c'*40}},
            base + '/git/tags/' + 'c'*40: {'object':{'type':'commit','sha':SHA}},
            base + '/releases/assets/42': {'id':42,'state':'uploaded','size':100,'name':'mod.zip','digest':'sha256:'+DIGEST,
                'browser_download_url':f'https://github.com/{REPO}/releases/download/v1.0/mod.zip'},
            base + '/releases/7/assets?per_page=100&page=1': [{'id':42}],
        }
        return values[path]

    @patch('scripts.author_publish.check')
    def test_asset_is_bound_to_tag_commit_digest_and_release_gate(self, gate):
        asset = verify_source(self.api, REPO, 'v1.0', SHA, '42', DIGEST)
        self.assertEqual(asset['id'], 42)
        gate.assert_called_once_with(self.api, REPO, 'refs/tags/v1.0', SHA)
        for field, value in [('draft',True), ('prerelease',True), ('tag_name','other')]:
            def api(path):
                result = self.api(path)
                if path.endswith('/releases/tags/v1.0'):
                    result[field] = value
                return result
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_source(api, REPO, 'v1.0', SHA, '42', DIGEST)

    @patch('scripts.author_publish.check')
    def test_substituted_asset_or_digest_or_owner_is_rejected(self, gate):
        for change in ('owner','digest','membership','url','commit'):
            def api(path):
                result = self.api(path)
                if change == 'owner' and path == f'repos/{REPO}':
                    result['owner']['id'] = 999
                if path.endswith('/releases/assets/42'):
                    if change == 'digest': result['digest'] = 'sha256:' + 'd'*64
                    if change == 'url': result['browser_download_url'] = 'https://evil.example/secret'
                if change == 'membership' and '/assets?per_page=' in path: return []
                if change == 'commit' and '/git/tags/' in path: result['object']['sha'] = 'd'*40
                return result
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_source(api, REPO, 'v1.0', SHA, '42', DIGEST)

    def test_download_never_authenticates_and_checks_bytes(self):
        class Opener:
            def open(self, request, timeout):
                self.request = request
                return io.BytesIO(b'payload')
        opener = Opener()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'payload.zip'
            asset = dict(browser_download_url='https://github.com/example',size=7)
            with patch('scripts.author_publish.inspect_archive', return_value={'verified':True}):
                self.assertEqual(fetch_payload(asset, hashlib.sha256(b'payload').hexdigest(), path, opener), {'verified':True})
            self.assertIsInstance(opener.request, str)
            with self.assertRaises(ValueError):
                fetch_payload(asset, '0'*64, Path(folder)/'bad.zip', opener)
            self.assertEqual(path.read_bytes(), b'payload')
            with self.assertRaises(FileExistsError):
                fetch_payload(asset, '0'*64, path, opener)

    def test_download_redirect_rejects_external_and_plaintext_hosts(self):
        handler = DownloadRedirects()
        for url in ('https://evil.example/a','http://github.com/a','https://user:pass@github.com/a'):
            with self.assertRaises(ValueError):
                handler.redirect_request(None, None, 302, '', {}, url)
