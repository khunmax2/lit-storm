import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend/demo_light"))
import article_store


class ArticleStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.alice = Path(article_store.workspace(self.root, "alice"))
        self.bob = Path(article_store.workspace(self.root, "bob"))

    def report(self, root, name="report", content="original report"):
        folder = root / name
        folder.mkdir()
        (folder / "storm_gen_article.txt").write_text(content)
        return folder

    def test_delete_and_restore_preserve_report_and_research_files(self):
        folder = self.report(self.alice)
        (folder / "conversation_log.json").write_text('[{"saved": true}]')
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        entry = article_store.trash_article(self.alice, "report")
        self.assertEqual(article_store.list_articles(self.alice), {})
        self.assertEqual(article_store.list_trash(self.alice), {entry: "report"})
        self.assertEqual(article_store.restore_article(self.alice, entry), "report")
        self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})
        self.assertEqual(article_store.list_trash(self.alice), {})

    def test_empty_failed_run_can_be_deleted_and_restored(self):
        (self.alice / "failed").mkdir()
        entry = article_store.trash_article(self.alice, "failed")
        article_store.restore_article(self.alice, entry)
        self.assertEqual(article_store.list_articles(self.alice), {"failed": {}})

    def test_users_cannot_restore_each_others_deleted_reports(self):
        self.report(self.alice)
        self.report(self.bob, content="bob report")
        entry = article_store.trash_article(self.alice, "report")
        self.assertEqual(article_store.list_trash(self.bob), {})
        with self.assertRaises(FileNotFoundError):
            article_store.restore_article(self.bob, entry)
        self.assertEqual((self.bob / "report/storm_gen_article.txt").read_text(), "bob report")

    def test_restoring_never_overwrites_a_new_report_with_the_same_name(self):
        self.report(self.alice)
        entry = article_store.trash_article(self.alice, "report")
        self.report(self.alice, content="new report")
        with self.assertRaises(FileExistsError):
            article_store.restore_article(self.alice, entry)
        self.assertEqual((self.alice / "report/storm_gen_article.txt").read_text(), "new report")
        self.assertEqual(article_store.list_trash(self.alice), {entry: "report"})

    def test_paths_and_reserved_names_are_rejected(self):
        for name in ("", "..", ".trash", "../bob/report", "/tmp/report", "bob\\report"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                article_store.trash_article(self.alice, name)
        with self.assertRaises(PermissionError):
            article_store.workspace(self.root, None)

    def test_symlinks_cannot_expose_or_move_another_users_reports(self):
        folder = self.report(self.bob)
        (self.alice / "linked").symlink_to(folder, target_is_directory=True)
        self.assertEqual(article_store.list_articles(self.alice), {})
        with self.assertRaises(ValueError):
            article_store.trash_article(self.alice, "linked")
        (self.alice / ".trash").symlink_to(self.bob, target_is_directory=True)
        with self.assertRaises(ValueError):
            article_store.list_trash(self.alice)
        (self.root / "linked-owner").symlink_to(self.bob, target_is_directory=True)
        with self.assertRaises(ValueError):
            article_store.workspace(self.root, "linked-owner")

    def test_empty_polished_article_falls_back_to_nonempty_draft(self):
        folder = self.report(self.alice)
        (folder / "storm_gen_article_polished.txt").write_text("  \n")
        files = article_store.list_articles(self.alice)["report"]
        self.assertEqual(article_store.completed_article(files), str(folder / "storm_gen_article.txt"))
        (folder / "storm_gen_article.txt").write_text("")
        self.assertIsNone(article_store.completed_article(files))


if __name__ == "__main__":
    unittest.main()
