"""Filing a report nobody is watching.

The manual import has a person in front of it who can retype a name or read
an error. The sync has neither, so the things that merely inconvenience an
import — a name already taken, a half-written history entry — are the things
that would silently lose a finished, paid-for report here.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend/demo_light"))

import article_store  # noqa: E402

REPORT = """# ผลการค้นคว้า

เนื้อหา [1]

## แหล่งอ้างอิง

1. [A source](https://example.test/a)
"""


def _sync():
    """The module, with its Streamlit component stubbed out.

    `declare_component` wants a running Streamlit to render into; nothing
    below renders anything, so it is replaced by a callable that is never
    called.
    """
    import streamlit.components.v1 as components

    with mock.patch.object(components, "declare_component", return_value=lambda **k: None):
        import research_sync

    return research_sync


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sync = _sync()

    def test_an_absent_ledger_reads_as_nothing_synced(self):
        self.assertEqual(self.sync.synced(self.root), {})

    def test_a_corrupt_ledger_reads_as_nothing_synced(self):
        """Half a write is not a reason to stop filing reports."""
        (self.root / self.sync.LEDGER).write_text("{not json", encoding="utf-8")
        self.assertEqual(self.sync.synced(self.root), {})

    def test_the_ledger_is_invisible_to_the_library(self):
        """It sits in the workspace beside the reports, and `list_articles`
        must not offer it as one."""
        self.sync._remember(self.root, "run-1", "Report")
        self.assertTrue((self.root / self.sync.LEDGER).is_file())
        self.assertEqual(article_store.list_articles(self.root), {})

    def test_what_was_filed_is_remembered_across_a_new_read(self):
        self.sync._remember(self.root, "run-1", "Report")
        self.sync._remember(self.root, "run-2", "Other")
        self.assertEqual(
            self.sync.synced(self.root), {"run-1": "Report", "run-2": "Other"}
        )


class NamingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sync = _sync()

    def test_a_free_name_is_left_alone(self):
        self.assertEqual(self.sync._free_name(self.root, "Sleep"), "Sleep")

    def test_a_taken_name_is_numbered_rather_than_refused(self):
        """Two runs on one topic produce one heading. Refusing the second is
        how a finished report disappears."""
        import article_import

        article_import.save(self.root, "Sleep", REPORT)
        self.assertEqual(self.sync._free_name(self.root, "Sleep"), "Sleep (2)")
        article_import.save(self.root, "Sleep (2)", REPORT)
        self.assertEqual(self.sync._free_name(self.root, "Sleep"), "Sleep (3)")

    def test_a_title_that_cannot_be_a_name_is_refused(self):
        """Only emptiness. A title with a slash in it is not refused — the
        slash becomes an underscore, which is what the article writer does
        with one too, and a usable name is better than a lost report."""
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError):
                self.sync._free_name(self.root, bad)

    def test_a_slash_is_flattened_rather_than_refused(self):
        import article_import

        name = self.sync._free_name(self.root, "a/b")
        article_store.validate_name(article_import.directory_name(name))


class FilingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sync = _sync()

    def handed(self, **over):
        report = {
            "id": "run-1",
            "title": "ผลการนอนหลับ",
            "query": "ผลการนอนหลับ",
            "report": REPORT,
            "createdAt": "2026-09-22T00:00:00Z",
        }
        report.update(over)
        return report

    def test_a_filed_report_is_a_finished_article_and_is_remembered(self):
        name = self.sync._file_report(self.root, self.handed())
        files = article_store.list_articles(self.root)[name]
        self.assertIsNotNone(article_store.completed_article(files))
        self.assertIn("url_to_info.json", files)
        self.assertEqual(self.sync.synced(self.root), {"run-1": name})

    def test_the_run_it_came_from_is_written_into_the_article(self):
        """So a report that arrived can say where from, long after."""
        name = self.sync._file_report(self.root, self.handed())
        info = json.loads(
            (self.root / name / "import_info.json").read_text(encoding="utf-8")
        )
        self.assertEqual(info["origin"], "deep-research:run-1")

    def test_the_query_stands_in_for_a_missing_title(self):
        name = self.sync._file_report(self.root, self.handed(title=""))
        self.assertTrue((self.root / name).is_dir())

    def test_a_report_with_no_title_at_all_is_refused(self):
        with self.assertRaises(ValueError):
            self.sync._file_report(self.root, self.handed(title="", query=""))

    def test_two_runs_on_one_topic_both_arrive(self):
        first = self.sync._file_report(self.root, self.handed())
        second = self.sync._file_report(self.root, self.handed(id="run-2"))
        self.assertNotEqual(first, second)
        self.assertEqual(len(article_store.list_articles(self.root)), 2)
        self.assertEqual(len(self.sync.synced(self.root)), 2)


if __name__ == "__main__":
    unittest.main()
