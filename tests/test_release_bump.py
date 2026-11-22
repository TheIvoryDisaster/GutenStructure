import json
import tempfile
import unittest
from pathlib import Path

from scripts.release_bump import bump, released


def release(asset, prerelease=False, draft=False):
    return {"prerelease": prerelease, "draft": draft, "assets": [{"name": asset}]}


class ReleaseBumpTests(unittest.TestCase):
    def manifest(self, temp, version):
        path = Path(temp) / "Mod" / "meitou.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"id": "x.mod", "version": version}))
        return path

    def test_only_a_production_release_holding_the_zip_counts(self):
        self.assertTrue(released([release("Mod-0.2.0.zip")], "Mod", "0.2.0"))
        self.assertFalse(released([release("Mod-0.2.0.zip", prerelease=True)], "Mod", "0.2.0"))
        self.assertFalse(released([release("Mod-0.2.0.zip", draft=True)], "Mod", "0.2.0"))
        self.assertFalse(released([release("Other-0.2.0.zip")], "Mod", "0.2.0"))

    def test_a_released_version_moves_to_the_next_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.manifest(temp, "0.2.0")
            notes = []
            self.assertEqual(bump(path, [release("Mod-0.2.0.zip")], notes), "0.2.1")
            self.assertEqual(json.loads(path.read_text())["version"], "0.2.1")
            self.assertEqual(len(notes), 1)

    def test_an_unreleased_version_already_carries_the_change(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.manifest(temp, "0.2.1")
            notes = []
            self.assertIsNone(bump(path, [release("Mod-0.2.0.zip")], notes))
            self.assertEqual(json.loads(path.read_text())["version"], "0.2.1")
            self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
