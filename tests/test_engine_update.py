import json
import tempfile
import unittest
from pathlib import Path

from scripts.engine_update import floored, main, newest, tag_of

TAGS = {
    "v0.22.1": "a" * 40,
    "v0.22.2-nightly.20261123": "b" * 40,
    "v0.22.2-nightly.20261123.2": "c" * 40,
    "v0.23.0": "d" * 40,
    "v0.23.1-nightly.20261125": "e" * 40,
    "fork-v0.23.0": "f" * 40,
}


class EngineUpdateTests(unittest.TestCase):
    def test_the_newest_build_is_a_nightly_above_the_newest_release(self):
        self.assertEqual(newest(TAGS), "v0.23.1-nightly.20261125")

    def test_a_release_beats_its_own_nightlies(self):
        self.assertEqual(newest({k: v for k, v in TAGS.items() if not k.startswith("v0.23.1")}), "v0.23.0")

    def test_a_second_build_of_the_day_beats_the_first(self):
        self.assertEqual(newest({k: TAGS[k] for k in ("v0.22.2-nightly.20261123", "v0.22.2-nightly.20261123.2")}), "v0.22.2-nightly.20261123.2")

    def test_a_fork_commit_has_no_tag(self):
        self.assertIsNone(tag_of(TAGS, "9" * 40))
        self.assertIsNone(tag_of(TAGS, "f" * 40))
        self.assertEqual(tag_of(TAGS, "d" * 40), "v0.23.0")

    def test_the_floor_moves_and_a_cap_it_reaches_goes(self):
        self.assertEqual(floored(">=0.22.2 <0.23.0", (0, 23, 1)), ">=0.23.1")
        self.assertEqual(floored(">=0.22.2 <0.24.0", (0, 23, 1)), ">=0.23.1 <0.24.0")
        self.assertEqual(floored(">=0.20.1", (0, 23, 1)), ">=0.23.1")
        self.assertEqual(floored("<0.24.0", (0, 23, 1)), ">=0.23.1 <0.24.0")


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "tags.json").write_text(json.dumps(TAGS))
        (self.root / "Directory.Build.rsp").write_text("-p:AssemblyVersion=0.22.2.0\n")
        (self.root / "Mod").mkdir()
        self.manifest = self.root / "Mod" / "meitou.json"
        self.manifest.write_text(json.dumps({"id": "m", "version": "0.1.0", "gameVersion": ">=0.22.2 <0.23.0"}))
        self.summary = self.root / "summary.md"

    def tearDown(self):
        self.dir.cleanup()

    def run_update(self, *extra, lock=None):
        (self.root / "meitou.lock.json").write_text(json.dumps({"format": 1, "frameworks": lock or []}))
        args = ["--root", str(self.root), "--tags", str(self.root / "tags.json"), "--summary", str(self.summary), *extra]
        from io import StringIO
        from contextlib import redirect_stdout
        out = StringIO()
        with redirect_stdout(out):
            main(args)
        return out.getvalue().strip()

    def test_an_old_pin_moves_to_the_newest_build_with_its_floor(self):
        self.assertEqual(self.run_update("--current", "b" * 40), "e" * 40)
        self.assertEqual((self.root / "Directory.Build.rsp").read_text(), "-p:AssemblyVersion=0.23.1.0\n")
        self.assertEqual(json.loads(self.manifest.read_text())["gameVersion"], ">=0.23.1")
        self.assertIn("v0.23.1-nightly.20261125", self.summary.read_text())

    def test_a_fork_commit_moves_too(self):
        self.assertEqual(self.run_update("--current", "9" * 40), "e" * 40)

    def test_the_newest_build_stays(self):
        self.assertEqual(self.run_update("--current", "e" * 40), "")
        self.assertEqual(json.loads(self.manifest.read_text())["gameVersion"], ">=0.22.2 <0.23.0")

    def test_a_repository_locking_frameworks_follows_them(self):
        self.assertEqual(self.run_update("--current", "b" * 40, lock=[{"id": "x"}]), "")

    def test_framework_update_moves_only_the_floor_to_the_locks_engine(self):
        self.assertEqual(self.run_update("--engine", "d" * 40, lock=[{"id": "x"}]), "")
        self.assertEqual((self.root / "Directory.Build.rsp").read_text(), "-p:AssemblyVersion=0.23.0.0\n")
        self.assertEqual(json.loads(self.manifest.read_text())["gameVersion"], ">=0.23.0")

    def test_an_untagged_lock_engine_leaves_the_floor(self):
        self.run_update("--engine", "9" * 40, lock=[{"id": "x"}])
        self.assertEqual((self.root / "Directory.Build.rsp").read_text(), "-p:AssemblyVersion=0.22.2.0\n")


if __name__ == "__main__":
    unittest.main()
