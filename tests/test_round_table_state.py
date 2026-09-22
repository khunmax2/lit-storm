"""When a discussion holds the front page, and when it lets go.

These two predicates decide whether the engine switch is drawn. They were one
predicate, and that is what trapped a reader on the round table: a discussion
that merely existed held the page, and the only control that released it also
discarded the discussion.

The distinction is narrow and worth pinning down: a discussion sitting still
must not hold the page, and work in flight must.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend/demo_light"))


class FakeState(dict):
    """`st.session_state` is a dict for everything these two functions do."""


def _round_table(state):
    """The module, with `st.session_state` replaced by `state`."""
    import streamlit as st
    from pages_util import RoundTable

    return RoundTable, mock.patch.object(st, "session_state", state)


class BusyAndWorkingTests(unittest.TestCase):
    def check(self, state, *, busy, working):
        module, patched = _round_table(FakeState(state))
        with patched:
            self.assertEqual(module.busy(), busy, f"busy for {state}")
            self.assertEqual(module.working(), working, f"working for {state}")

    def test_nothing_started(self):
        self.check({}, busy=False, working=False)

    def test_idle_is_not_a_discussion(self):
        self.check({"costorm_state": "idle"}, busy=False, working=False)

    def test_a_warm_start_holds_the_page(self):
        """It runs a mini-STORM synchronously; navigate away and it never runs."""
        self.check({"costorm_state": "warming"}, busy=True, working=True)

    def test_an_open_discussion_does_not_hold_the_page(self):
        """The whole point: open, idle, and the reader may leave and come back."""
        self.check({"costorm_state": "open"}, busy=True, working=False)

    def test_a_queued_turn_holds_the_page(self):
        """`_queue` sets this and reruns; only the round table pops and runs it."""
        self.check(
            {"costorm_state": "open", "costorm_pending": "turn"},
            busy=True,
            working=True,
        )

    def test_a_queued_report_holds_the_page(self):
        self.check(
            {"costorm_state": "open", "costorm_pending": "report"},
            busy=True,
            working=True,
        )

    def test_a_finished_turn_releases_the_page(self):
        """`_round_table` pops the marker before doing the work, so the run
        after it is free again."""
        self.check(
            {"costorm_state": "open", "costorm_folder": "some/report"},
            busy=True,
            working=False,
        )


class StateKeysTests(unittest.TestCase):
    def test_discussion_state_survives_a_page_sweep(self):
        """`clear_other_page_session_state` deletes keys beginning with "page".
        A discussion is meant to outlive navigation, so none of its keys may
        start with that — otherwise leaving Co-STORM would silently lose it,
        which is exactly what the page used to be protecting against."""
        from pages_util import RoundTable

        for key in RoundTable.STATE_KEYS:
            self.assertFalse(
                key.startswith("page"), f"{key} would be swept on navigation"
            )


if __name__ == "__main__":
    unittest.main()
