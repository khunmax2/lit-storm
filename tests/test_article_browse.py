"""Which report is at the top of the library, and which ones are shown.

The default matters more here than it looks. A library only grows, and the
report somebody wants is nearly always the one they have just made — which
alphabetical order buries in the middle.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend/demo_light"))

import article_browse as browse  # noqa: E402


class Library(unittest.TestCase):
    """A workspace on disk, since every decision here is made from files."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, when=None, *, finished=True, extra=None, origin=None):
        folder = self.root / name
        folder.mkdir()
        if finished:
            (folder / "storm_gen_article_polished.txt").write_text(
                "an article", encoding="utf-8"
            )
        else:
            (folder / "conversation_log.json").write_text("[]", encoding="utf-8")
        for filename in extra or ():
            (folder / filename).write_text("{}", encoding="utf-8")
        if origin is not None:
            (folder / "import_info.json").write_text(
                json.dumps({"origin": origin}), encoding="utf-8"
            )
        if when is not None:
            for path in folder.iterdir():
                os.utime(path, (when, when))
        return {p.name: str(p) for p in folder.iterdir()}

    def library(self, **entries):
        return entries


class OrderTests(Library):
    def setUp(self):
        super().setUp()
        base = time.time() - 10_000
        self.articles = {
            "Bravo": self.write("Bravo", base + 200),
            "Alpha": self.write("Alpha", base + 100),
            "Charlie": self.write("Charlie", base + 300),
        }

    def test_newest_first_is_the_default(self):
        self.assertEqual(
            browse.arrange(self.articles), ["Charlie", "Bravo", "Alpha"]
        )

    def test_oldest_first_is_the_reverse(self):
        self.assertEqual(
            browse.arrange(self.articles, sort=browse.OLDEST),
            ["Alpha", "Bravo", "Charlie"],
        )

    def test_by_title_ignores_the_dates(self):
        self.assertEqual(
            browse.arrange(self.articles, sort=browse.NAME),
            ["Alpha", "Bravo", "Charlie"],
        )

    def test_reports_written_in_the_same_second_keep_a_stable_order(self):
        """Otherwise two cards swap places between renders for no reason."""
        same = time.time() - 500
        tied = {
            "Zulu": self.write("Zulu", same),
            "Alpha2": self.write("Alpha2", same),
            "Mike": self.write("Mike", same),
        }
        first = browse.arrange(tied)
        self.assertEqual(first, browse.arrange(tied))
        self.assertEqual(first, ["Alpha2", "Mike", "Zulu"])
        # and the tiebreak points the same way when the dates are reversed
        self.assertEqual(browse.arrange(tied, sort=browse.OLDEST), first)

    def test_an_unfinished_run_is_dated_by_what_it_did_write(self):
        base = time.time() - 50
        articles = {"Stopped": self.write("Stopped", base, finished=False)}
        self.assertAlmostEqual(browse.when_of(articles["Stopped"]), base, places=0)


class OriginTests(Library):
    def test_an_article_with_nothing_special_is_storm(self):
        files = self.write("Plain")
        self.assertEqual(browse.origin_of(files), browse.STORM)

    def test_a_saved_discussion_is_costorm(self):
        files = self.write("Talked", extra=["costorm_conversation.json"])
        self.assertEqual(browse.origin_of(files), browse.COSTORM)

    def test_the_conversation_log_alone_does_not_mean_costorm(self):
        """STORM writes one too, from its perspective interviews."""
        files = self.write("Interviewed", extra=["conversation_log.json"])
        self.assertEqual(browse.origin_of(files), browse.STORM)

    def test_a_synced_report_names_the_engine_that_wrote_it(self):
        self.assertEqual(
            browse.origin_of(self.write("D", origin="deep-research:run-1")),
            browse.DEEP_RESEARCH,
        )
        self.assertEqual(
            browse.origin_of(self.write("A", origin="agents-research:run-2")),
            browse.AGENTS_RESEARCH,
        )

    def test_a_hand_carried_file_is_imported(self):
        self.assertEqual(
            browse.origin_of(self.write("Manual", origin="report.md")),
            browse.IMPORTED,
        )
        self.assertEqual(
            browse.origin_of(self.write("Blank", origin="")), browse.IMPORTED
        )

    def test_an_unreadable_record_does_not_raise(self):
        files = self.write("Broken")
        Path(files["storm_gen_article_polished.txt"]).parent.joinpath(
            "import_info.json"
        ).write_text("{not json", encoding="utf-8")
        files["import_info.json"] = str(
            Path(files["storm_gen_article_polished.txt"]).parent / "import_info.json"
        )
        self.assertEqual(browse.origin_of(files), browse.IMPORTED)


class FilterTests(Library):
    def setUp(self):
        super().setUp()
        self.articles = {
            "S": self.write("S"),
            "C": self.write("C", extra=["costorm_conversation.json"]),
            "D": self.write("D", origin="deep-research:1"),
            "Stopped": self.write("Stopped", finished=False),
        }

    def test_filtering_by_origin(self):
        self.assertEqual(browse.arrange(self.articles, show=browse.COSTORM), ["C"])
        self.assertEqual(
            browse.arrange(self.articles, show=browse.DEEP_RESEARCH), ["D"]
        )

    def test_filtering_to_the_runs_that_never_finished(self):
        self.assertEqual(
            browse.arrange(self.articles, show=browse.UNFINISHED), ["Stopped"]
        )

    def test_no_filter_shows_everything(self):
        self.assertEqual(len(browse.arrange(self.articles, show=browse.ALL)), 4)

    def test_only_the_origins_that_are_actually_here_are_offered(self):
        """A filter offering choices that match nothing wastes a click."""
        offered = browse.origins_present(self.articles)
        self.assertEqual(offered, [browse.STORM, browse.COSTORM, browse.DEEP_RESEARCH])
        self.assertNotIn(browse.AGENTS_RESEARCH, offered)

    def test_the_unfinished_filter_is_offered_only_when_one_exists(self):
        self.assertTrue(browse.has_unfinished(self.articles))
        finished_only = {"S": self.articles["S"]}
        self.assertFalse(browse.has_unfinished(finished_only))


if __name__ == "__main__":
    unittest.main()
