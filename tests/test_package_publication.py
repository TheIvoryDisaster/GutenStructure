import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.publish_meitou_package import publish
from scripts.release_gate import MissingResource


class PackagePublicationTests(unittest.TestCase):
    def setup_case(self,folder,existing=False,head=None,existing_digest=None,rolling_head=None):
        self.sha='a'*40
        self.label='0.6.0-beta.aaaaaaa'
        self.tag='framework-'+self.label
        self.filename='Framework-'+self.label+'.zip'
        self.digest=hashlib.sha256(b'fixture bytes').hexdigest()
        path=Path(folder)
        (path/self.filename).write_bytes(b'fixture bytes')
        (path/(self.filename+'.sha256')).write_text(self.digest+'  '+self.filename+'\n')
        (path/'notes.md').write_text('fixture notes')
        self.commands=[]
        def api(route):
            if '/compare/' in route:
                if rolling_head and route.endswith(rolling_head+'...'+self.sha):return {'status':'behind' if rolling_head=='b'*40 else 'ahead'}
                return {'status':'identical' if head is None else 'ahead'}
            if route.endswith('/branches/beta'):return {'commit':{'sha':head or self.sha}}
            if '/releases/tags/' in route:
                tag=route.rsplit('/',1)[1]
                if tag=='framework-beta' and rolling_head:return {'id':2,'tag_name':tag,'draft':False,'prerelease':True}
                if existing and tag==self.tag:return {'id':1,'tag_name':tag,'draft':False,'prerelease':True}
                raise MissingResource('fixture')
            if '/git/ref/tags/' in route:
                if route.endswith('/framework-beta') and rolling_head:return {'object':{'type':'commit','sha':rolling_head}}
                if existing:return {'object':{'type':'commit','sha':self.sha}}
                raise MissingResource('fixture')
            if '/releases/1/assets?' in route:return [
                {'name':self.filename,'state':'uploaded','digest':'sha256:'+(existing_digest or self.digest)},
                {'name':self.filename+'.sha256','state':'uploaded'}]
            raise AssertionError(route)
        return api,path

    def call(self,api,path,**kwargs):
        return publish(api,self.commands.append,'Meitou-Modding-Ecosystem/RivalryCore',self.sha,
            kwargs.get('ref','refs/heads/beta'),'Framework','framework',kwargs.get('channel','beta'),
            kwargs.get('label',self.label),self.digest,path)

    def test_new_snapshot_and_current_head_rolling_are_published(self):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder)
            result=self.call(api,path)
            self.assertEqual(len(self.commands),2)
            self.assertTrue(result['rolling_updated'])
            self.assertIn(str(path/'Framework-beta.zip.sha256'),self.commands[-1])

    def test_old_build_publishes_snapshot_but_never_rolls_back_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder,head='b'*40,rolling_head='b'*40)
            result=self.call(api,path)
            self.assertEqual(len(self.commands),1)
            self.assertFalse(result['rolling_updated'])

    def test_equal_existing_snapshot_is_verified_not_recreated(self):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder,existing=True,head='b'*40,rolling_head='b'*40)
            result=self.call(api,path)
            self.assertTrue(result['existing_verified'])
            self.assertEqual(self.commands,[])
            self.assertEqual(result['sha256'],self.digest)

    def test_changed_rerun_bytes_fail_without_any_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder,existing=True,existing_digest='0'*64)
            with self.assertRaisesRegex(ValueError,'canonical artifact'):
                self.call(api,path)
            self.assertEqual(self.commands,[])

    def test_existing_tag_mismatch_fails_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder,existing=True)
            def wrong(route):
                if '/git/ref/tags/' in route:return {'object':{'type':'commit','sha':'c'*40}}
                return api(route)
            with self.assertRaisesRegex(ValueError,'another source'):
                self.call(wrong,path)
            self.assertEqual(self.commands,[])

    def test_beta_cannot_publish_from_another_branch(self):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder)
            with self.assertRaisesRegex(ValueError,'requires beta'):
                self.call(api,path,ref='refs/heads/development')
            self.assertEqual(self.commands,[])

    @patch('scripts.publish_meitou_package.check_release',side_effect=RuntimeError('not protected release head'))
    def test_production_refuses_a_nonrelease_commit_before_writes(self,gate):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder)
            with self.assertRaisesRegex(RuntimeError,'not protected'):
                self.call(api,path,channel='release',ref='refs/tags/framework-v0.6.0',label='0.6.0')
            gate.assert_called_once_with(api,'Meitou-Modding-Ecosystem/RivalryCore','refs/tags/framework-v0.6.0',self.sha)
            self.assertEqual(self.commands,[])


class ProductionPositiveTests(unittest.TestCase):
    setup_case=PackagePublicationTests.setup_case
    call=PackagePublicationTests.call
    @patch('scripts.publish_meitou_package.check_release')
    def test_reviewed_production_package_can_publish(self,gate):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder)
            label='0.6.0'
            filename='Framework-'+label+'.zip'
            (path/self.filename).rename(path/filename)
            (path/(filename+'.sha256')).write_text(self.digest+'  '+filename+'\n')
            result=self.call(api,path,channel='release',ref='refs/tags/framework-v0.6.0',label=label)
            self.assertEqual(result['tag'],'framework-v0.6.0')
            self.assertFalse(result['rolling_updated'])
            self.assertEqual(len(self.commands),1)
            self.assertNotIn('--prerelease',self.commands[0])
            gate.assert_called_once()


class DocumentationOnlyAdvanceTests(unittest.TestCase):
    setup_case=PackagePublicationTests.setup_case
    call=PackagePublicationTests.call
    def test_beta_docs_commit_does_not_suppress_newest_framework_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            api,path=self.setup_case(folder,head='b'*40,rolling_head='c'*40)
            result=self.call(api,path)
            self.assertTrue(result['rolling_updated'])
            self.assertEqual(len(self.commands),3)
