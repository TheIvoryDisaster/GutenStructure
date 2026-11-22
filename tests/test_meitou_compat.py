import json
import tempfile
import unittest
from pathlib import Path

from scripts.meitou_compat import Check, Mod, decide, lifted, parse_tags, targets, write


class MeitouCompatTests(unittest.TestCase):
    TAGS = ["v0.21.0", "v0.22.0", "v0.22.1", "v0.22.2-nightly.20261121", "v0.22.2-nightly.20261121.2", "v0.22.2-nightly.20261122",
            "v0.22.1-nightly.20261101", "fork-v0.22.1", "v0.22.1^{}"]

    def setUp(self):
        self.full, self.nightly = parse_tags(self.TAGS)

    def test_tags_split_into_full_releases_and_nightlies_oldest_first(self):
        self.assertEqual([r.tag for r in self.full], ["v0.21.0", "v0.22.0", "v0.22.1"])
        self.assertEqual(self.nightly[-1].tag, "v0.22.2-nightly.20261122")
        self.assertEqual(self.nightly[-2].tag, "v0.22.2-nightly.20261121.2")

    def test_targets_are_the_newest_release_a_newer_nightly_and_each_floor(self):
        chosen = targets(self.full, self.nightly, [">=0.21.0 <0.22.2", ">=0.22.0 <0.22.2"])
        self.assertEqual([(kind, r.tag) for kind, r in chosen],
                         [("release", "v0.22.1"), ("nightly", "v0.22.2-nightly.20261122"), ("floor", "v0.21.0"), ("floor", "v0.22.0")])

    def test_a_range_without_a_floor_has_no_floor_check(self):
        self.assertEqual([kind for kind, _ in targets(self.full, self.nightly, ["", "<0.23.0"])], ["release", "nightly"])

    def test_a_nightly_older_than_the_newest_release_is_not_checked(self):
        full, nightly = parse_tags(["v0.22.1", "v0.22.1-nightly.20261101"])
        self.assertEqual([kind for kind, _ in targets(full, nightly, [])], ["release"])

    def test_a_cap_moves_to_the_next_patch_above_a_release_it_excludes(self):
        release = self.full[-1]
        self.assertEqual(lifted(">=0.22.0 <0.22.1", release), ">=0.22.0 <0.22.2")
        self.assertIsNone(lifted(">=0.22.0 <0.22.2", release))  # already admitted
        self.assertIsNone(lifted(">=0.22.0", release))  # no cap
        self.assertIsNone(lifted(">=0.23.0 <0.24.0", release))  # excluded from below

    def outcome(self, checks, apis):
        mods = [Mod("Mod", Path("Mod/meitou.json"), ">=0.22.0 <0.22.1")]
        return decide(mods, checks, self.full[-1], apis, {"Mod": "v0.22.0"})

    def test_a_clean_release_above_the_cap_with_the_same_api_lifts_it(self):
        result = self.outcome([Check("v0.22.1", "release", "Mod/Mod.dll", [], [])], {"v0.22.0": 2, "v0.22.1": 2})
        self.assertEqual(result["lifts"], {"Mod": ">=0.22.0 <0.22.2"})
        self.assertEqual(result["issues"], [])

    def test_a_changed_code_mod_api_asks_a_person_instead(self):
        result = self.outcome([Check("v0.22.1", "release", "Mod/Mod.dll", [], [])], {"v0.22.0": 2, "v0.22.1": 3})
        self.assertEqual(result["lifts"], {})
        self.assertIn("code-mod API changed (2 → 3)", result["issues"][0])

    def test_a_missing_member_in_the_release_is_an_issue_and_no_lift(self):
        result = self.outcome([Check("v0.22.1", "release", "Mod/Mod.dll", ["A::B()"], [])], {"v0.22.0": 2, "v0.22.1": 2})
        self.assertEqual(result["lifts"], {})
        self.assertEqual(len(result["issues"]), 2)

    def test_a_nightly_break_is_only_a_warning(self):
        checks = [Check("v0.22.1", "release", "Mod/Mod.dll", [], []), Check("v0.22.2-nightly.20261122", "nightly", "Mod/Mod.dll", ["A::B()"], [])]
        mods = [Mod("Mod", Path("Mod/meitou.json"), ">=0.22.0 <0.22.2")]
        result = decide(mods, checks, self.full[-1], {}, {"Mod": "v0.22.1"})
        self.assertEqual(result["issues"], [])
        self.assertEqual(len(result["warnings"]), 1)

    def test_a_floor_above_the_newest_release_is_only_a_warning(self):
        mods = [Mod("Mod", Path("Mod/meitou.json"), ">=0.22.2 <0.23.0")]
        result = decide(mods, [Check("v0.22.1", "release", "Mod/Mod.dll", [], [])], self.full[-1], {}, {"Mod": None})
        self.assertEqual(result["issues"], [])
        self.assertIn("loads only in nightlies", result["warnings"][0])

    def test_a_newer_engine_stamp_than_the_floor_is_an_issue(self):
        mods = [Mod("Mod", Path("Mod/meitou.json"), ">=0.21.0 <0.22.2")]
        checks = [Check("v0.21.0", "floor", "Mod/Mod.dll", [], ["MeitouClient 0.22.0.0 > 0.21.0.0"])]
        self.assertIn("engine stamp", decide(mods, checks, self.full[-1], {}, {"Mod": "v0.22.1"})["issues"][0])

    def test_the_lift_writes_only_the_lifted_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            (root / "Mod").mkdir(parents=True)
            (root / "Mod" / "meitou.json").write_text(json.dumps({"id": "x.mod", "gameVersion": ">=0.22.0 <0.22.1"}))
            mods = [Mod("Mod", root / "Mod" / "meitou.json", ">=0.22.0 <0.22.1")]
            out = Path(temp) / "out"
            write(out, root, mods, [], {"issues": [], "warnings": [], "lifts": {"Mod": ">=0.22.0 <0.22.2"}}, self.full[-1])
            self.assertEqual(json.loads((out / "lift" / "Mod" / "meitou.json").read_text())["gameVersion"], ">=0.22.0 <0.22.2")
            self.assertIn("Needs a release", (out / "lift.md").read_text())
            self.assertFalse((out / "issue.md").exists())


if __name__ == "__main__":
    unittest.main()
