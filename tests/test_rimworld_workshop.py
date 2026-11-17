import hashlib
import io
import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.rimworld_workshop import fetch_release, stage


class RimWorldWorkshopTests(unittest.TestCase):
    def payload(self, path, change=None):
        files = {
            'Mod/About/About.xml': b'<ModMetaData><packageId>author.mod</packageId><modVersion>1</modVersion><supportedVersions><li>1.6</li></supportedVersions></ModMetaData>',
            'Mod/About/PublishedFileId.txt': b'123456',
            'Mod/About/Preview.png': b'\x89PNG\r\n\x1a\n'+b'\0'*4+b'IHDR'+(640).to_bytes(4,'big')+(360).to_bytes(4,'big'),
            'Mod/1.6/Assemblies/Mod.dll': b'test fixture only',
        }
        if change:
            change(files)
        with zipfile.ZipFile(path,'w') as output:
            for name, content in files.items():
                output.writestr(name, content)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_valid_package_stages_existing_item_without_upload_or_visibility(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            digest = self.payload(root/'mod.zip')
            result = stage(root/'mod.zip', root/'stage', digest, 'author.mod', '123456')
            self.assertEqual(result['supported_versions'], ['1.6'])
            self.assertFalse(result['uploaded'])
            vdf = (root/'stage/workshop-preview.vdf').read_text()
            self.assertIn('"appid" "294100"', vdf)
            self.assertIn('"publishedfileid" "123456"', vdf)
            self.assertNotIn('"visibility"', vdf)
            self.assertTrue((root/'stage/Mod/1.6/Assemblies/Mod.dll').is_file())
            with self.assertRaises(FileExistsError):
                stage(root/'mod.zip', root/'stage', digest, 'author.mod', '123456')

    def test_mismatch_missing_assembly_unsafe_and_redistributed_game_dll_rejected(self):
        changes = [
            lambda fs: fs.update({'Mod/About/PublishedFileId.txt':b'999'}),
            lambda fs: fs.update({'Mod/About/About.xml':fs['Mod/About/About.xml'].replace(b'1.6',b'1.7')}),
            lambda fs: fs.update({'Mod/../escape':b'bad'}),
            lambda fs: fs.update({'Mod/1.6/Assemblies/Assembly-CSharp.dll':b'bad'}),
            lambda fs: fs.update({'Mod/About/Preview.png':b'not PNG'}),
            lambda fs: fs.update({'Mod/Source/private.txt':b'bad'}),
            lambda fs: fs.update({'BadRoot\"/file':b'bad'}),
        ]
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                digest=self.payload(root/'mod.zip',change)
                with self.assertRaises((ValueError, KeyError)):
                    stage(root/'mod.zip',root/'stage',digest,'author.mod','123456')
                self.assertFalse((root/'stage').exists())

    def test_digest_and_zero_id_fail_before_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            digest=self.payload(root/'mod.zip')
            for checksum, item in [('0'*64,'123456'),(digest,'0')]:
                with self.assertRaises(ValueError):
                    stage(root/'mod.zip',root/'stage',checksum,'author.mod',item)
            self.assertFalse((root/'stage').exists())

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.payload(root/'mod.zip')
            with zipfile.ZipFile(root/'mod.zip','a') as archive:
                link=zipfile.ZipInfo('Mod/link')
                link.external_attr=(stat.S_IFLNK|0o777)<<16
                archive.writestr(link,'../../escape')
            digest=hashlib.sha256((root/'mod.zip').read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                stage(root/'mod.zip',root/'stage',digest,'author.mod','123456')

    def test_private_release_is_fetched_only_from_caller_and_bound_to_main_history(self):
        repo='ExampleAuthor/ExampleMod'
        commit='a'*40
        payload=b'opaque fixture'
        digest=hashlib.sha256(payload).hexdigest()
        data={
            f'repos/{repo}':{'id':100,'owner':{'id':200,'type':'User'},'default_branch':'main','private':True},
            f'repos/{repo}/releases/tags/v1':{'id':1,'draft':False,'prerelease':False,'tag_name':'v1'},
            f'repos/{repo}/git/ref/tags/v1':{'object':{'type':'commit','sha':commit}},
            f'repos/{repo}/compare/{commit}...main':{'status':'ahead'},
            f'repos/{repo}/releases/assets/2':{'digest':'sha256:'+digest,'state':'uploaded','size':len(payload),'name':'Mod-1.zip'},
            f'repos/{repo}/releases/1/assets?per_page=100&page=1':[{'id':2}],
        }
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{'GITHUB_REPOSITORY':repo,'GITHUB_REPOSITORY_ID':'100','GITHUB_REPOSITORY_OWNER_ID':'200'}), patch('scripts.rimworld_workshop.gh_api',side_effect=lambda path:data[path]), patch('scripts.rimworld_workshop.subprocess.run') as download:
            path=Path(folder)/'release.zip'
            download.side_effect=lambda *args,**kwargs:path.write_bytes(payload)
            self.assertEqual(fetch_release('v1','2',digest,path),commit)
            self.assertIn('--repo',download.call_args.args[0])
            self.assertIn(repo,download.call_args.args[0])
            data[f'repos/{repo}/compare/{commit}...main']['status']='diverged'
            with self.assertRaises(ValueError):
                fetch_release('v1','2',digest,path)
