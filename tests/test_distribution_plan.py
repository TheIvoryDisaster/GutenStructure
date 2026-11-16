import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.distribution_plan import load_registry, plan, workshop_vdf


class DistributionPlanTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry('distribution/targets.json')

    def test_all_registered_mods_are_explicit_noops(self):
        for mod in self.registry['mods']:
            result = plan(self.registry, mod, '1.2.3')
            self.assertFalse(result['would_publish'])
            self.assertEqual(result['mode'], 'dry-run')
            self.assertTrue(result['steam']['blockers'])
            self.assertTrue(result['nexus']['blockers'])

    def test_destination_configuration_cannot_turn_on_uploads(self):
        target = self.registry['mods']['rivalry-core']
        target['author'] = 'ExampleAuthor'
        target['steam'].update(published_file_id=123456, validated_for_kenshi=True)
        target['nexus'].update(mod_id=123, file_id=456)
        result = plan(self.registry, 'rivalry-core', '1.2.3')
        self.assertFalse(result['would_publish'])
        self.assertEqual(result['steam']['blockers'], [])
        self.assertEqual(result['nexus']['blockers'], [])
        self.assertTrue(result['blockers'])

    def test_registry_rejects_live_flag_wrong_game_and_zero_ids(self):
        for change in ('live', 'game', 'zero', 'boolean-id'):
            registry = copy.deepcopy(self.registry)
            target = registry['mods']['rivalry-core']
            if change == 'live':
                registry['live_publishing_enabled'] = True
            elif change == 'game':
                target['steam']['app_id'] = 480
            else:
                target['steam']['published_file_id'] = 0 if change == 'zero' else True
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'registry.json'
                path.write_text(json.dumps(registry))
                with self.assertRaises(ValueError):
                    load_registry(path)

    def test_workshop_preview_never_creates_items_or_injects_vdf(self):
        target = self.registry['mods']['rivalry-core']['steam']
        with self.assertRaises(ValueError):
            workshop_vdf(target, '/tmp/staging', '1.0')
        target['published_file_id'] = 123456
        preview = workshop_vdf(target, '/tmp/staging', '1.0')
        self.assertIn('"publishedfileid" "123456"', preview)
        self.assertIn('"appid" "233860"', preview)
        self.assertNotIn('login', preview)
        for path in ['/tmp/a"\n"publishedfileid" "0', '/tmp/a\\b', 'relative']:
            with self.assertRaises(ValueError):
                workshop_vdf(target, path, '1.0')

    def test_payload_identity_and_missing_fcs_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Rivalry/Rivalry.mod', b'fixture, not game data')
            result = plan(self.registry, 'rivalry-core', '1.0', path)
            self.assertEqual(len(result['payload']['sha256']), 64)
            self.assertEqual(result['payload']['files'], 1)
            self.assertFalse(result['would_publish'])
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('README.md', 'incomplete package')
            with self.assertRaisesRegex(ValueError, 'No FCS'):
                plan(self.registry, 'rivalry-core', '1.0', path)

    def test_unsafe_archive_entries_are_rejected_without_extraction(self):
        for entry in ('../escape.mod', '/absolute.mod', 'C:/absolute.mod', 'a\\escape.mod'):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'bad.zip'
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr(entry, b'fixture')
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    plan(self.registry, 'rivalry-core', '1.0', path)

    def test_version_cannot_inject_commands_or_vdf(self):
        for version in ('1.0\nlogin', '$(id)', '1"0', '../1.0'):
            with self.assertRaises(ValueError):
                plan(self.registry, 'rivalry-core', version)
