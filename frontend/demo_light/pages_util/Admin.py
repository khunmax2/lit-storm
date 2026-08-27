"""The roster: who has an account, what they may do, and what they have used.

Reachable only by an admin, and only *shown* here — the row-level policies in
docs/supabase-schema.sql are what actually refuse a member's write.
"""

import auth
import pandas as pd
import streamlit as st
import ui_theme
from ui_language import t

ROLES = ["member", "admin"]
EDITABLE = ("role", "monthly_run_limit", "is_active")


def _roster_frame(profiles, usage):
    return pd.DataFrame(
        [
            {
                "id": row["id"],
                t("admin.col_name"): row.get("display_name") or "",
                t("admin.col_email"): row.get("email", ""),
                t("admin.col_role"): row.get("role", "member"),
                t("admin.col_limit"): int(row.get("monthly_run_limit", 0)),
                t("admin.col_used"): usage.get(row["id"], 0),
                t("admin.col_active"): bool(row.get("is_active", True)),
                t("admin.col_joined"): (row.get("created_at") or "")[:10],
            }
            for row in profiles
        ]
    )


def _apply_edits(edited, profiles):
    """Write back only the rows that actually changed. Returns how many."""
    by_id = {row["id"]: row for row in profiles}
    columns = {
        "role": t("admin.col_role"),
        "monthly_run_limit": t("admin.col_limit"),
        "is_active": t("admin.col_active"),
    }
    written = 0
    for record in edited.to_dict("records"):
        original = by_id.get(record["id"])
        if original is None:
            continue
        changes = {}
        for field in EDITABLE:
            new = record[columns[field]]
            if field == "monthly_run_limit":
                new = max(0, int(new))
            elif field == "is_active":
                new = bool(new)
            elif new not in ROLES:
                continue
            if new != original.get(field):
                changes[field] = new
        if changes:
            auth.update_profile(record["id"], **changes)
            written += 1
    return written


def _recent_runs(profiles):
    runs = auth.recent_runs()
    if not runs:
        st.caption(t("admin.runs_empty"))
        return
    names = {
        row["id"]: (row.get("display_name") or row.get("email", "")) for row in profiles
    }
    st.dataframe(
        pd.DataFrame(
            [
                {
                    t("admin.col_topic"): run.get("topic", ""),
                    t("admin.col_who"): names.get(run.get("user_id"), ""),
                    t("admin.col_status"): run.get("status", ""),
                    t("admin.col_when"): (run.get("started_at") or "")[:16].replace(
                        "T", " "
                    ),
                }
                for run in runs
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )


def admin_page():
    if not auth.is_admin():
        ui_theme.page_header(t("admin.title"))
        st.error(t("admin.denied"))
        return

    profiles = auth.list_profiles()
    usage = auth.usage_since_month_start()
    ui_theme.page_header(t("admin.title"), t("admin.count", n=len(profiles)))

    if auth.admin_count(profiles) < 2:
        st.info(t("admin.last_admin"), icon=":material/info:")

    frame = _roster_frame(profiles, usage)
    edited = st.data_editor(
        frame,
        hide_index=True,
        use_container_width=True,
        key="admin_roster",
        column_config={
            "id": None,
            t("admin.col_name"): st.column_config.TextColumn(disabled=True),
            t("admin.col_email"): st.column_config.TextColumn(disabled=True),
            t("admin.col_used"): st.column_config.NumberColumn(disabled=True),
            t("admin.col_joined"): st.column_config.TextColumn(disabled=True),
            t("admin.col_role"): st.column_config.SelectboxColumn(options=ROLES),
            t("admin.col_limit"): st.column_config.NumberColumn(
                min_value=0, step=1, help=t("admin.help_limit")
            ),
            t("admin.col_active"): st.column_config.CheckboxColumn(),
        },
    )

    if st.button(t("admin.save"), type="primary"):
        written = _apply_edits(edited, profiles)
        if written:
            st.success(t("admin.saved", n=written))
            st.rerun()
        else:
            st.info(t("admin.no_changes"))

    ui_theme.section_label(t("admin.runs_label"))
    _recent_runs(profiles)
