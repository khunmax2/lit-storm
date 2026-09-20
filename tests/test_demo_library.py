"""Report actions and account changes, using synthetic reports and no API calls."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend/demo_light"))


class DemoLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache_dir = tempfile.TemporaryDirectory()
        from litellm.caching.caching import Cache

        class TempCache(Cache):
            def __init__(self, *args, **kwargs):
                kwargs["disk_cache_dir"] = cls.cache_dir.name
                super().__init__(*args, **kwargs)

        with patch.dict(os.environ, {"DSP_CACHEDIR": cls.cache_dir.name}), patch(
            "litellm.caching.caching.Cache", TempCache
        ):
            import demo_util
        import auth
        from streamlit.testing.v1 import AppTest
        cls.auth = auth
        cls.demo_util = demo_util
        cls.AppTest = AppTest

    @classmethod
    def tearDownClass(cls):
        cls.cache_dir.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "DEMO_WORKING_DIR/alice"
        self.root.mkdir(parents=True)

    def library(self):
        return self.AppTest.from_string(f'''
import streamlit as st
import auth
import demo_util
from unittest.mock import patch
from pages_util import MyArticles
st.session_state.setdefault('ui_lang', 'ไทย')
with patch.object(auth, 'user_id', return_value='alice'), patch.object(
    demo_util, 'get_demo_dir', return_value={self.temp.name!r}
):
    MyArticles.my_articles_page()
''').run()

    def assert_no_errors(self, app):
        self.assertFalse(app.exception, [error.message for error in app.exception])

    def test_failed_report_details_button_opens_an_empty_run(self):
        (self.root / "failed").mkdir()
        app = self.library()
        self.assert_no_errors(app)
        self.assertFalse(app.button(key="open_failed").disabled)
        app.button(key="open_failed").click().run()
        self.assert_no_errors(app)
        self.assertEqual(app.session_state["page2_selected_my_article"], "failed")
        self.assertTrue(any("ก่อนที่จะมีการบันทึก" in message.value for message in app.info))

    def test_saved_outline_and_research_are_readable_without_a_finished_report(self):
        folder = self.root / "partial"
        folder.mkdir()
        (folder / "storm_gen_outline.txt").write_text("# Saved outline\nA saved section")
        (folder / "raw_search_results.json").write_text(json.dumps({
            "https://example.com": {"title": "Saved source", "snippets": ["Saved evidence"]}
        }))
        (folder / "run_config.json").write_text('{"api_key": "DO_NOT_DISPLAY_THIS"}')
        app = self.library()
        app.button(key="open_partial").click().run()
        self.assert_no_errors(app)
        rendered = "\n".join(element.value for element in app.markdown)
        self.assertIn("Saved outline", rendered)
        self.assertIn("Saved source", rendered)
        self.assertIn("Saved evidence", rendered)
        self.assertNotIn("DO_NOT_DISPLAY_THIS", rendered)

    def test_malformed_research_file_shows_a_message_without_crashing(self):
        folder = self.root / "partial"
        folder.mkdir()
        (folder / "conversation_log.json").write_text("{incomplete")
        app = self.library()
        app.button(key="open_partial").click().run()
        self.assert_no_errors(app)
        self.assertTrue(any("ข้อมูลส่วนนี้ไม่สมบูรณ์" in message.value for message in app.warning))

    def test_delete_and_restore_from_the_library(self):
        folder = self.root / "failed"
        folder.mkdir()
        app = self.library()
        app.button(key="delete_failed").click().run()
        self.assert_no_errors(app)
        self.assertFalse(folder.exists())
        self.assertTrue(any("ย้าย" in message.value for message in app.success))
        restore = next(button for button in app.button if (button.key or "").startswith("restore_"))
        restore.click().run()
        self.assert_no_errors(app)
        self.assertTrue(folder.is_dir())
        self.assertFalse(app.button(key="open_failed").disabled)

    def test_nonempty_draft_opens_when_polishing_left_an_empty_file(self):
        folder = self.root / "draft"
        folder.mkdir()
        (folder / "storm_gen_article.txt").write_text("# Summary\nReadable draft content")
        (folder / "storm_gen_article_polished.txt").write_text("")
        app = self.library()
        self.assert_no_errors(app)
        self.assertEqual(app.button(key="open_draft").label, "อ่านบทความ")
        app.button(key="open_draft").click().run()
        self.assert_no_errors(app)
        self.assertTrue(any("Readable draft content" in element.value for element in app.markdown))

    def test_completed_report_can_be_deleted_from_its_reading_page(self):
        folder = self.root / "ready"
        folder.mkdir()
        (folder / "storm_gen_article.txt").write_text("# Summary\nReport content")
        app = self.library()
        app.button(key="open_ready").click().run()
        self.assert_no_errors(app)
        app.button(key="delete_selected_ready").click().run()
        self.assert_no_errors(app)
        self.assertFalse(folder.exists())
        self.assertNotIn("page2_selected_my_article", app.session_state)

    def test_cached_runner_is_rebuilt_when_the_workspace_changes(self):
        state = {}
        settings = (("fake-fast", {"api_key": "test"}), ("fake-strong", {"api_key": "test"}))
        with patch.object(self.demo_util.st, "session_state", state), patch.object(
            self.demo_util, "lm_settings", return_value=settings
        ), patch.object(self.demo_util, "working_dir", side_effect=["alice", "bob", "bob"]), patch.object(
            self.demo_util, "LitellmModel"
        ), patch.object(self.demo_util.search_sources, "build"), patch.object(
            self.demo_util, "STORMWikiRunner", side_effect=lambda args, *_: SimpleNamespace(args=args)
        ) as factory:
            self.demo_util.set_storm_runner()
            self.assertEqual(state["runner"].args.output_dir, "alice")
            self.demo_util.set_storm_runner()
            self.assertEqual(state["runner"].args.output_dir, "bob")
            self.demo_util.set_storm_runner()
            self.assertEqual(factory.call_count, 2)

    def test_library_does_not_reuse_a_previous_accounts_cached_file_paths(self):
        (self.root / "own_report").mkdir()
        app = self.AppTest.from_string(f'''
import auth, demo_util, streamlit as st
from unittest.mock import patch
from pages_util.MyArticles import _load_articles
st.session_state['page2_user_articles_file_path_dict'] = {{'other_users_private_report': {{}}}}
with patch.object(auth, 'user_id', return_value='alice'), patch.object(
    demo_util, 'get_demo_dir', return_value={self.temp.name!r}
):
    st.write(list(_load_articles()))
''').run()
        self.assert_no_errors(app)
        self.assertIn("own_report", app.json[0].value)
        self.assertNotIn("other_users_private_report", app.json[0].value)

    def test_signout_discards_previous_accounts_files_and_runners(self):
        state = {
            "page2_user_articles_file_path_dict": {"private": {}},
            "page2_selected_my_article": "private", "costorm_runner": object(),
            "costorm_topic": "private", "runner": object(), "runner_settings": "same",
            "runner_workspace": "alice", "nav_page": "Members",
            "ui_lang": "ไทย", "auth_client": Mock(), "auth_session": object(),
        }
        with patch.object(self.auth.st, "session_state", state), patch.object(
            self.auth, "dev_mode", return_value=False
        ), patch.object(self.auth, "_clear_cookie"):
            self.auth.sign_out()
        self.assertEqual(state, {"ui_lang": "ไทย"})

    def test_signin_as_another_user_discards_previous_workspace_state(self):
        state = {
            "auth_session": SimpleNamespace(user=SimpleNamespace(id="alice")),
            "runner": object(), "costorm_runner": object(),
            "page2_selected_my_article": "private", "ui_lang": "ไทย",
        }
        new_session = SimpleNamespace(user=SimpleNamespace(id="bob"), refresh_token=None)
        with patch.object(self.auth.st, "session_state", state):
            self.auth._remember(new_session)
        self.assertNotIn("runner", state)
        self.assertNotIn("costorm_runner", state)
        self.assertNotIn("page2_selected_my_article", state)
        self.assertEqual(state["auth_session"].user.id, "bob")
        self.assertEqual(state["ui_lang"], "ไทย")

    def test_supabase_clients_are_distinct_between_real_streamlit_sessions(self):
        with patch("supabase.create_client", side_effect=lambda *_: object()) as factory, patch.object(
            self.auth, "setting", return_value="test-setting"
        ):
            script = 'import auth, streamlit as st\nst.write(str(id(auth._client())))'
            alice = self.AppTest.from_string(script).run()
            bob = self.AppTest.from_string(script).run()
            alice_id = alice.markdown[0].value
            self.assertNotEqual(alice_id, bob.markdown[0].value)
            alice.run()
            self.assertEqual(alice_id, alice.markdown[0].value)
            self.assertEqual(factory.call_count, 2)


if __name__ == "__main__":
    unittest.main()
