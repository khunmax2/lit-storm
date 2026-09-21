"""What an imported report has to survive on the way in.

The interesting cases are all about citations. Deep Research writes `[1]`
against the index of its evidence, and the library resolves `[1]` through
`url_to_unified_index` — so if the numbers shift by one, every reference in
the article points at the wrong source and nothing anywhere says so.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend/demo_light"))
import article_import


DEEP_RESEARCH = """# ผลกระทบของ AI ต่อการศึกษาไทย

บทนำ [1] และอีกประโยค [2]

## Sources

[1] NECTEC — https://www.nectec.or.th/news.html
[2] [Ministry of Education](https://moe.go.th/ai)
"""


class SourceParsingTests(unittest.TestCase):
    def test_numbers_in_the_list_are_the_numbers_the_body_cites(self):
        sources = article_import.parse_sources(DEEP_RESEARCH)
        self.assertEqual(
            sources,
            [
                (1, "NECTEC", "https://www.nectec.or.th/news.html"),
                (2, "Ministry of Education", "https://moe.go.th/ai"),
            ],
        )

    def test_a_list_that_numbers_itself_keeps_its_own_numbers(self):
        """A report may cite [5] first; renumbering would silently misattribute."""
        text = "# T\n\n## References\n\n[5] Five - https://five.example\n" \
               "[9] Nine - https://nine.example\n"
        self.assertEqual(
            [number for number, _, _ in article_import.parse_sources(text)], [5, 9]
        )

    def test_an_unnumbered_list_is_numbered_by_the_order_it_was_written(self):
        text = "# T\n\n## Sources\n\n- [A](https://a.example)\n- [B](https://b.example)\n"
        self.assertEqual(
            article_import.parse_sources(text),
            [(1, "A", "https://a.example"), (2, "B", "https://b.example")],
        )

    def test_the_last_sources_heading_wins(self):
        """A report that discusses its sources before listing them."""
        text = (
            "# T\n\n## Sources\n\nWe used three kinds.\n\n"
            "## Method\n\ntext\n\n## References\n\n[1] Real - https://real.example\n"
        )
        self.assertEqual(
            article_import.parse_sources(text),
            [(1, "Real", "https://real.example")],
        )

    def test_the_block_stops_at_the_next_heading_of_the_same_level(self):
        text = (
            "# T\n\n## Sources\n\n[1] A - https://a.example\n\n"
            "## Appendix\n\nsee https://not-a-source.example\n"
        )
        urls = [url for _, _, url in article_import.parse_sources(text)]
        self.assertEqual(urls, ["https://a.example"])

    def test_a_thai_heading_is_a_sources_heading(self):
        text = "# T\n\n## แหล่งอ้างอิง\n\n[1] ก - https://thai.example\n"
        self.assertEqual(
            article_import.parse_sources(text), [(1, "ก", "https://thai.example")]
        )

    def test_no_list_is_an_empty_list_not_an_error(self):
        self.assertEqual(article_import.parse_sources("# T\n\nbody only\n"), [])

    def test_the_same_url_twice_is_kept_once(self):
        text = "# T\n\n## Sources\n\n[1] A - https://a.example\n[2] A again - https://a.example\n"
        self.assertEqual(len(article_import.parse_sources(text)), 1)


class CitationFileTests(unittest.TestCase):
    def test_the_file_is_the_shape_the_library_reads(self):
        built = article_import.citations(article_import.parse_sources(DEEP_RESEARCH))
        self.assertEqual(
            built["url_to_unified_index"],
            {"https://www.nectec.or.th/news.html": 1, "https://moe.go.th/ai": 2},
        )
        record = built["url_to_info"]["https://moe.go.th/ai"]
        # `_construct_citation_dict_from_search_result` indexes both of these
        # without a default, so a missing key is a KeyError on open.
        self.assertEqual(record["title"], "Ministry of Education")
        self.assertEqual(record["snippets"], [])

    def test_no_sources_means_no_file(self):
        self.assertIsNone(article_import.citations([]))


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_saved_report_is_a_finished_article_to_the_rest_of_the_app(self):
        import article_store

        name = article_import.save(self.root, "My Report", DEEP_RESEARCH)
        self.assertEqual(name, "My_Report")
        files = article_store.list_articles(self.root)[name]
        self.assertIsNotNone(article_store.completed_article(files))
        self.assertIn("url_to_info.json", files)
        stored = json.loads(Path(files["url_to_info.json"]).read_text(encoding="utf-8"))
        self.assertEqual(len(stored["url_to_unified_index"]), 2)

    def test_the_title_is_taken_from_the_reports_own_heading(self):
        self.assertEqual(
            article_import.suggested_title(DEEP_RESEARCH, "whatever.md"),
            "ผลกระทบของ AI ต่อการศึกษาไทย",
        )

    def test_a_report_with_no_heading_falls_back_to_the_file_name(self):
        self.assertEqual(
            article_import.suggested_title("no heading here", "deep_research_run.md"),
            "deep research run",
        )

    def test_an_import_never_overwrites_a_report_that_is_already_there(self):
        article_import.save(self.root, "Report", DEEP_RESEARCH)
        with self.assertRaises(FileExistsError):
            article_import.save(self.root, "Report", DEEP_RESEARCH)
        # and the first one is untouched
        kept = (self.root / "Report" / article_import.ARTICLE_FILE).read_text(
            encoding="utf-8"
        )
        self.assertEqual(kept, DEEP_RESEARCH)

    def test_a_long_thai_title_fits_the_filesystem_not_just_the_character_count(self):
        """Thai is three bytes a character; 125 of them is 375, and ext4 stops
        at 255. The first real import failed on exactly this."""
        title = "ประโยชน์ของการนอนหลับให้เพียงพอต่อสุขภาพสมองและอารมณ์ รายงานสังเคราะห์หลักฐานสำหรับกลุ่มคนวัยทำงาน"
        name = article_import.directory_name(title)
        self.assertLessEqual(len(name.encode("utf-8")), 255)
        # and the cut is on a character boundary, not through one
        self.assertEqual(name, name.encode("utf-8").decode("utf-8"))
        # it still writes, which is the whole point
        article_import.save(self.root, title, DEEP_RESEARCH)
        self.assertTrue((self.root / name).is_dir())

    def test_a_title_that_escapes_the_workspace_is_refused(self):
        for bad in ("../elsewhere", ".hidden", "", "   "):
            with self.assertRaises(ValueError):
                article_import.save(self.root, bad, DEEP_RESEARCH)

    def test_an_empty_report_is_refused_before_a_directory_is_made(self):
        with self.assertRaises(ValueError):
            article_import.save(self.root, "Empty", "   \n  ")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_a_report_without_sources_still_imports(self):
        name = article_import.save(self.root, "Plain", "# Plain\n\nbody\n")
        files = {p.name for p in (self.root / name).iterdir()}
        self.assertIn(article_import.ARTICLE_FILE, files)
        self.assertNotIn(article_import.CITATIONS_FILE, files)


if __name__ == "__main__":
    unittest.main()
