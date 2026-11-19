import datetime
import unittest
from scripts.pr_digest import chunk, classify, render, window

UTC = datetime.timezone.utc


class PrDigestTests(unittest.TestCase):
    def test_window_is_previous_new_york_day_across_dst(self):
        start, end, day = window("America/New_York", datetime.datetime(2026, 11, 2, 12, tzinfo=UTC))
        self.assertEqual(day, datetime.date(2026, 11, 1))
        self.assertEqual(start, datetime.datetime(2026, 11, 1, 4, tzinfo=UTC))
        self.assertEqual(end, datetime.datetime(2026, 11, 2, 5, tzinfo=UTC))

    def test_most_significant_event_wins(self):
        since, until = datetime.datetime(2026, 11, 17, 5, tzinfo=UTC), datetime.datetime(2026, 11, 18, 5, tzinfo=UTC)
        inside, before = "2026-11-17T12:00:00Z", "2026-11-10T12:00:00Z"
        pull = {"merged_at": inside, "closed_at": inside, "created_at": inside}
        self.assertEqual(classify(pull, since, until), "merged")
        self.assertEqual(classify({**pull, "merged_at": None}, since, until), "closed")
        self.assertEqual(classify({"merged_at": None, "closed_at": None, "created_at": inside}, since, until), "opened")
        self.assertEqual(classify({"merged_at": None, "closed_at": None, "created_at": before}, since, until), "updated")

    def test_plain_listing_without_summary_and_no_pings(self):
        pull = {"number": 3, "title": "Thank @someone", "url": "u", "author": "a", "base": "beta", "event": "opened"}
        text = render(datetime.date(2026, 11, 17), {"o/r": [pull]}, {"o/r": None})
        self.assertIn("**Opened**", text)
        self.assertNotIn("<details>", text)
        self.assertNotIn("@someone", text)

    def test_chunks_fit_discord_and_break_between_lines(self):
        text = "\n".join(["x" * 900] * 5 + ["y" * 4500])
        pieces = chunk(text, 2000)
        self.assertTrue(all(len(p) <= 2000 for p in pieces))
        self.assertEqual("".join(pieces).replace("\n", ""), text.replace("\n", ""))
        self.assertEqual(pieces[0], "\n".join(["x" * 900] * 2))


if __name__ == "__main__":
    unittest.main()
