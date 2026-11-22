import json
import tempfile
import unittest
from pathlib import Path

from scripts.framework_update import Candidate, candidates, is_newer, newest, satisfies, widen, widen_manifests, zip_asset


def release(tag, published="2026-11-18T00:00:00Z", prerelease=False, assets=()):
    return {"tag_name": tag, "published_at": published, "prerelease": prerelease, "draft": False, "body": "", "assets": list(assets)}


class FrameworkUpdateTests(unittest.TestCase):
    RELEASES = [
        release("rivalry-core-v0.6.0", "2026-11-18T01:00:00Z"),
        release("rivalry-core-v0.6.1", "2026-11-19T01:00:00Z"),
        release("rivalry-core-0.7.0-beta.abc1234", "2026-11-20T01:00:00Z", prerelease=True),
        release("rivalry-core-0.7.0-beta.def5678", "2026-11-21T01:00:00Z", prerelease=True),
        release("rivalry-core-beta", "2026-11-21T01:00:00Z", prerelease=True),
        release("logistics-core-v1.0.0"),
    ]

    def test_release_channel_takes_the_highest_production_version(self):
        found = candidates(self.RELEASES, "rivalry-core", "release")
        self.assertEqual({c.tag for c in found}, {"rivalry-core-v0.6.0", "rivalry-core-v0.6.1"})
        self.assertEqual(newest(found, "release").tag, "rivalry-core-v0.6.1")

    def test_beta_channel_takes_the_latest_snapshot_never_the_rolling_tag(self):
        found = candidates(self.RELEASES, "rivalry-core", "beta")
        self.assertNotIn("rivalry-core-beta", {c.tag for c in found})
        self.assertEqual(newest(found, "beta").tag, "rivalry-core-0.7.0-beta.def5678")

    def test_newer_means_higher_version_or_later_build_of_the_same(self):
        snapshot = Candidate("rivalry-core-0.6.0-beta.def5678", (0, 6, 0), "2026-11-21", "", ())
        self.assertFalse(is_newer(Candidate("rivalry-core-v0.6.0", (0, 6, 0), "x", "", ()), "rivalry-core-v0.6.0", "x"))
        self.assertTrue(is_newer(Candidate("rivalry-core-v0.6.1", (0, 6, 1), "", "", ()), "rivalry-core-v0.6.0", "2026-11-18"))
        self.assertTrue(is_newer(snapshot, "rivalry-core-0.6.0-beta.abc1234", "2026-11-20"))
        self.assertFalse(is_newer(snapshot, "rivalry-core-0.6.0-beta.abc1234", "2026-11-22"))

    def test_zip_asset_skips_the_rolling_beta_zip(self):
        assets = ({"name": "RivalryCore-0.7.0-beta.def5678.zip"}, {"name": "RivalryCore-beta.zip"}, {"name": "notes.txt"})
        self.assertEqual(zip_asset(Candidate("t", (0, 7, 0), "", "", assets), "RivalryCore")["name"], "RivalryCore-0.7.0-beta.def5678.zip")
        with self.assertRaises(ValueError):
            zip_asset(Candidate("t", (0, 7, 0), "", "", ()), "RivalryCore")

    def test_ranges_widen_only_their_upper_bound(self):
        self.assertTrue(satisfies(">=0.6.0 <0.7.0", (0, 6, 1)))
        self.assertFalse(satisfies(">=0.6.0 <0.7.0", (0, 7, 0)))
        self.assertIsNone(widen(">=0.6.0 <0.7.0", (0, 6, 1)))
        self.assertEqual(widen(">=0.6.0 <0.7.0", (0, 7, 0)), ">=0.6.0 <0.8.0")
        self.assertEqual(widen(">=1.0.0 <2.0.0", (2, 1, 0)), ">=1.0.0 <3.0.0")
        self.assertIsNone(widen(">=0.8.0 <0.9.0", (0, 7, 0)))

    def test_manifests_with_excluding_ranges_are_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Mod").mkdir()
            manifest = {"id": "ashen.hand", "dependencies": [{"id": "rivalry.core", "version": ">=0.6.0 <0.7.0"}]}
            (root / "Mod" / "meitou.json").write_text(json.dumps(manifest))
            notes = []
            changed = widen_manifests(root, {"rivalry.core": (0, 7, 0)}, notes)
            self.assertEqual(changed, [root / "Mod" / "meitou.json"])
            self.assertEqual(widen_manifests(root, {"rivalry.core": (0, 7, 1)}, notes), [])
            written = json.loads((root / "Mod" / "meitou.json").read_text())
            self.assertEqual(written["dependencies"][0]["version"], ">=0.6.0 <0.8.0")
            self.assertEqual(len(notes), 1)


if __name__ == "__main__":
    unittest.main()
