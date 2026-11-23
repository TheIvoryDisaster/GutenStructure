import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = json.loads((ROOT / "registry" / "numbers.json").read_text(encoding="utf-8"))
DOC = (ROOT / "docs" / "numbers.md").read_text(encoding="utf-8")


class NumberBlockTests(unittest.TestCase):
    def test_blocks_are_aligned_and_above_the_first_mod_number(self):
        size = REGISTRY["blockSize"]
        for block in REGISTRY["blocks"]:
            self.assertGreaterEqual(block["first"], REGISTRY["first"], block)
            self.assertEqual(block["first"] % size, 0, block)

    def test_blocks_do_not_overlap_and_each_mod_has_one(self):
        firsts = [b["first"] for b in REGISTRY["blocks"]]
        mods = [b["mod"] for b in REGISTRY["blocks"]]
        self.assertEqual(len(firsts), len(set(firsts)))
        self.assertEqual(len(mods), len(set(mods)))

    def test_doc_table_matches_the_registry(self):
        size = REGISTRY["blockSize"]
        rows = re.findall(r"^\| (\d+)-(\d+) \| `([^`]+)` \|", DOC, re.MULTILINE)
        listed = {(int(a), int(b), mod) for a, b, mod in rows}
        expected = {(b["first"], b["first"] + size - 1, b["mod"]) for b in REGISTRY["blocks"]}
        self.assertEqual(listed, expected)


if __name__ == "__main__":
    unittest.main()
