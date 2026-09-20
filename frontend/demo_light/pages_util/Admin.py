"""Member roster, filters and protected edits."""

import auth
from html import escape
import pandas as pd
import streamlit as st
import ui_theme
from member_management import EDITABLE, MAX_LIMIT, ROLES, MemberManagementError, pending_edits
from member_roster import filter_members, page_members, PAGE_SIZE
from ui_language import t


def _queue_reset():
    st.session_state["admin_reset_pending"] = True


def _reset_editor(profiles):
    st.session_state.pop("admin_edit_baselines", None)
    for row in profiles:
        target = row["id"]
        st.session_state[f"admin_edit_role_{target}"] = row["role"]
        st.session_state[f"admin_edit_active_{target}"] = row["is_active"]
        st.session_state[f"admin_edit_limit_{target}"] = row["monthly_run_limit"]


def _source_label(source):
    return t(f"admin.source_{source}") if source in (
        "self_signup", "admin_create", "first_sign_in", "legacy_unknown"
    ) else t("admin.source_legacy_unknown")


def _member_editor(profiles, usage):
    actor = auth.user_id()
    names = {row["id"]: row.get("display_name") or row.get("email", "") for row in profiles}
    baselines = st.session_state.setdefault("admin_edit_baselines", {})
    role_labels = {value: t(f"auth.role_{value}") for value in ROLES}
    status_labels = {True: t("admin.active"), False: t("admin.suspended")}
    role_filter_labels = {"all": t("admin.all_roles"), **role_labels}
    status_filter_labels = {"all": t("admin.all_statuses"), "active": status_labels[True], "suspended": status_labels[False]}

    search, role_filter, status_filter = st.columns([2.6, 1, 1], vertical_alignment="bottom")
    with search:
        query = st.text_input(t("admin.search"), key="admin_search",
            placeholder=t("admin.search_placeholder"), icon=":material/search:",
            label_visibility="collapsed")
    with role_filter:
        selected_role = st.selectbox(t("admin.role_filter"),
            ["all", *ROLES], format_func=role_filter_labels.__getitem__,
            key="admin_role_filter", label_visibility="collapsed")
    with status_filter:
        selected_status = st.selectbox(t("admin.status_filter"),
            ["all", "active", "suspended"],
            format_func=status_filter_labels.__getitem__,
            key="admin_status_filter", label_visibility="collapsed")
    visible = filter_members(profiles, query, selected_role, selected_status)
    visible.sort(key=lambda row: (row["id"] != actor, (row.get("display_name") or row.get("email") or "").casefold()))
    page = st.session_state.get("admin_list_page", 1)
    shown, page, total_pages = page_members(visible, page)
    st.session_state["admin_list_page"] = page

    columns = [2.6, 1.15, 1.45, 1.55, 1.0, 1.25, 1.2]
    with st.container(key="admin_roster_table"):
        with st.container(key="admin_roster_header"):
            for column, label in zip(st.columns(columns, vertical_alignment="center"),
                ["admin.member", "admin.col_role", "admin.col_active", "admin.used_this_month",
                 "admin.monthly_limit", "admin.col_joined", "admin.actions"]):
                with column:
                    st.caption(t(label))
        if not shown:
            st.info(t("admin.no_results"), icon=":material/search_off:")
        for row in shown:
            target = row["id"]
            own = target == actor
            st.session_state.setdefault(f"admin_edit_role_{target}", row["role"])
            st.session_state.setdefault(f"admin_edit_active_{target}", row["is_active"])
            st.session_state.setdefault(f"admin_edit_limit_{target}", row["monthly_run_limit"])
            if target not in baselines:
                baselines[target] = {"id": target, **{key: row[key] for key in EDITABLE}}
            for widget_field, profile_field in (("role", "role"), ("active", "is_active"), ("limit", "monthly_run_limit")):
                widget_key = f"admin_edit_{widget_field}_{target}"
                if st.session_state[widget_key] is None:
                    st.session_state[widget_key] = baselines[target][profile_field]
            current = {"id": target,
                "role": st.session_state[f"admin_edit_role_{target}"],
                "is_active": st.session_state[f"admin_edit_active_{target}"],
                "monthly_run_limit": int(st.session_state[f"admin_edit_limit_{target}"])}
            used = usage.get(target, 0)
            limit = int(row.get("monthly_run_limit", 0))
            joined = (row.get("account_created_at") or row.get("created_at") or "")[:10]
            with st.container(key=f"admin_roster_row_{target}"):
                member_col, role_col, state_col, usage_col, limit_col, joined_col, action_col = st.columns(
                    columns, vertical_alignment="center")
                with member_col:
                    name = escape(row.get("display_name") or row.get("email") or "")
                    email = escape(row.get("email") or "")
                    initial = escape((row.get("display_name") or row.get("email") or "?")[:1].upper())
                    st.markdown(f'<div class="member-identity"><span class="member-avatar">{initial}</span>'
                        f'<span><strong>{name}</strong><small>{email}</small></span></div>',
                        unsafe_allow_html=True)
                    if own:
                        st.badge(t("admin.you"), icon=":material/person:", color="blue")
                with role_col:
                    st.markdown(f'<span class="mobile-cell-label">{t("admin.col_role")}</span>', unsafe_allow_html=True)
                    st.badge(role_labels[row["role"]], color="blue" if row["role"] == "admin" else "gray")
                with state_col:
                    st.markdown(f'<span class="mobile-cell-label">{t("admin.col_active")}</span>', unsafe_allow_html=True)
                    st.badge(status_labels[bool(row.get("is_active", True))],
                        icon=":material/circle:", color="green" if row.get("is_active", True) else "red")
                with usage_col:
                    st.markdown(f'<span class="mobile-cell-label">{t("admin.used_this_month")}</span>', unsafe_allow_html=True)
                    st.markdown(f"**{used} / {limit}** {t('admin.times')}")
                    ratio = used / limit if limit else (1 if used else 0)
                    st.progress(min(ratio, 1.0))
                    if used > limit:
                        st.caption(t("admin.over_quota", n=used - limit))
                with limit_col:
                    st.markdown(f'<span class="mobile-cell-label">{t("admin.monthly_limit")}</span>', unsafe_allow_html=True)
                    st.markdown(f"**{limit}** {t('admin.times')}")
                with joined_col:
                    st.markdown(f'<span class="mobile-cell-label">{t("admin.col_joined")}</span>', unsafe_allow_html=True)
                    st.text(joined or "—")
                    st.caption(_source_label(row.get("created_via", "legacy_unknown")))
                with action_col:
                    with st.popover(t("admin.actions"), icon=":material/more_vert:", key=f"admin_action_{target}",
                        help=t("admin.edit_member"), width="stretch"):
                        st.markdown(f"**{t('admin.edit_member')}: {name}**")
                        if own:
                            st.caption(t("admin.self_protected"))
                        role = st.selectbox(t("admin.col_role"), ROLES,
                            index=0, format_func=role_labels.__getitem__,
                            disabled=own, key=f"admin_edit_role_{target}", persist_state="session")
                        active = st.selectbox(t("admin.col_active"), [True, False],
                            index=0, format_func=status_labels.__getitem__,
                            disabled=own, key=f"admin_edit_active_{target}", persist_state="session")
                        monthly = st.number_input(t("admin.col_limit"), min_value=0,
                            max_value=MAX_LIMIT, step=1, value="min",
                            help=t("admin.help_limit"), key=f"admin_edit_limit_{target}",
                            persist_state="session")
                        creator = names.get(row.get("created_by"), row.get("created_by") or "")
                        if creator:
                            st.caption(t("admin.created_by", name=creator))
                        st.caption(t("admin.edit_then_save"))
                        current.update(role=role, is_active=active, monthly_run_limit=int(monthly))
    first = (page - 1) * PAGE_SIZE + 1 if visible else 0
    last = min(page * PAGE_SIZE, len(visible))
    count, controls = st.columns([3, 2], vertical_alignment="center")
    with count:
        st.caption(t("admin.showing", start=first, end=last, total=len(visible)))
    with controls:
        if total_pages > 1:
            st.pagination(total_pages, key="admin_list_page", width="stretch")
    # Hidden pages keep their unsaved edits in session state. Include every
    # touched member, so changing a filter never silently discards a change.
    candidates = []
    for row in profiles:
        target = row["id"]
        if target not in baselines:
            continue
        candidates.append({"id": target,
            "role": st.session_state.get(f"admin_edit_role_{target}", row["role"]),
            "is_active": st.session_state.get(f"admin_edit_active_{target}", row["is_active"]),
            "monthly_run_limit": int(st.session_state.get(f"admin_edit_limit_{target}", row["monthly_run_limit"]))})
    return pending_edits(list(baselines.values()), candidates, actor)


def _save_changes(edits):
    info, save, reset = st.columns([3, 2, 1], vertical_alignment="center")
    with info:
        st.caption(t("admin.pending", n=len(edits)) if edits else t("admin.no_changes"))
    with save:
        submitted = st.button(t("admin.save"), key="admin_save", type="primary",
            disabled=not edits, width="stretch")
    with reset:
        st.button(t("admin.reset"), key="admin_reset", disabled=not edits,
            on_click=_queue_reset, width="stretch")
    if submitted:
        try:
            written = auth.update_profiles(edits)
        except MemberManagementError as error:
            st.error(t(f"admin.error_{error}"))
        except Exception:  # noqa: BLE001 - no provider secrets in the UI
            st.error(t("admin.save_failed"))
        else:
            st.session_state["admin_flash"] = t("admin.saved", n=written)
            st.session_state["admin_reset_pending"] = True
            st.rerun()


def _create_member_form():
    available = auth.admin_creation_configured() and not auth.dev_mode()
    st.caption(t("admin.create_help"))
    if not available:
        st.info(t("admin.create_setup"))
    with st.form("admin_create_member", clear_on_submit=True):
        name = st.text_input(t("auth.name"), key="admin_create_name")
        email = st.text_input(t("auth.email"), key="admin_create_email")
        password = st.text_input(t("auth.password"), type="password", key="admin_create_password")
        verified = st.checkbox(t("admin.email_verified"), key="admin_create_verified")
        submitted = st.form_submit_button(t("admin.add_member"), type="primary", disabled=not available)
    if submitted:
        if not verified:
            st.warning(t("admin.verify_email_first"))
            return
        try:
            auth.create_member(email, password, name)
        except MemberManagementError as error:
            st.error(t(f"admin.error_{error}"))
        except Exception:
            st.error(t("admin.create_not_ready"))
        else:
            st.session_state["admin_flash"] = t("admin.created")
            st.rerun()


def _open_create_member():
    @st.dialog(t("admin.add_member"), icon=":material/person_add:")
    def dialog():
        _create_member_form()
    dialog()


def _recent_runs(profiles):
    runs = auth.recent_runs()
    if not runs:
        st.caption(t("admin.runs_empty"))
        return
    names = {row["id"]: row.get("display_name") or row.get("email", "") for row in profiles}
    st.dataframe(pd.DataFrame([{
        t("admin.col_topic"): run.get("topic", ""),
        t("admin.col_who"): names.get(run.get("user_id"), ""),
        t("admin.col_status"): t("admin.run_" + run.get("status", "running")),
        t("admin.col_when"): (run.get("started_at") or "")[:16].replace("T", " "),
    } for run in runs]), hide_index=True, width="stretch")


def _audit_history(profiles):
    try:
        events = auth.recent_member_events()
    except Exception:  # noqa: BLE001 - existing installations need the migration
        st.info(t("admin.audit_setup"))
        return
    if not events:
        st.caption(t("admin.audit_empty"))
        return
    names = {row["id"]: row.get("display_name") or row.get("email", "") for row in profiles}
    st.caption(t("admin.audit_help"))
    for event in events:
        timestamp = (event.get("occurred_at") or "")[:19].replace("T", " ")
        target = names.get(event.get("target_id"), (event.get("details") or {}).get("email") or event.get("target_id") or "—")
        label = t("admin.event_" + event["event"])
        with st.expander(f"{timestamp} · {label}"):
            st.text(t("admin.event_target", name=target))
            actor = names.get(event.get("actor_id"), event.get("actor_id") or t("admin.system"))
            st.text(t("admin.created_by", name=actor))
            st.caption(t("admin.event_outcome", outcome=t("admin.outcome_" + event["outcome"])))
            if event.get("source") != "admin_edit":
                st.caption(_source_label(event.get("source")))
            before, after = event.get("before_values") or {}, event.get("after_values") or {}
            columns = {"email": "admin.col_email", "display_name": "admin.col_name",
                "role": "admin.col_role", "monthly_run_limit": "admin.col_limit", "is_active": "admin.col_active"}
            def display(field, value):
                if value is None:
                    return "—"
                if field == "role":
                    return t("auth.role_" + value)
                if field == "is_active":
                    return t("admin.active" if value else "admin.suspended")
                return str(value)
            rows = [{t("admin.field"): t(columns[field]),
                t("admin.before"): display(field, before.get(field)),
                t("admin.after"): display(field, after.get(field))}
                for field in columns if field in before or field in after]
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            reason = (event.get("details") or {}).get("reason")
            if reason in ("auth_rejected", "profile_registration_failed", "rollback_failed"):
                st.caption(t("admin.reason_" + reason))


def admin_page():
    if not auth.is_admin():
        ui_theme.page_header(t("admin.title"))
        st.error(t("admin.denied"))
        return
    profiles = auth.list_profiles()
    if st.session_state.pop("admin_reset_pending", False):
        _reset_editor(profiles)
    usage = auth.usage_since_month_start()
    with st.container(key="admin_dashboard"):
        title_col, add_col = st.columns([4, 1], vertical_alignment="center")
        with title_col:
            st.title(t("admin.title"))
            st.caption(t("admin.subtitle"))
        with add_col:
            if st.button(t("admin.add_member"), key="admin_open_create", icon=":material/add:",
                type="primary", width="stretch"):
                _open_create_member()
        flash = st.session_state.pop("admin_flash", None)
        if flash:
            st.success(flash)
        active = sum(bool(row.get("is_active", True)) for row in profiles)
        suspended = len(profiles) - active
        metrics = st.columns(3)
        for column, key, value, caption, icon in zip(metrics,
            ["total", "active", "suspended"], [len(profiles), active, suspended],
            [t("admin.total_caption"), t("admin.active_caption", pct=round(active / len(profiles) * 100) if profiles else 0),
             t("admin.suspended_caption", pct=round(suspended / len(profiles) * 100) if profiles else 0)],
            ["group", "check_circle", "block"]):
            with column:
                with st.container(key=f"admin_stat_{key}"):
                    st.markdown(f'<span class="admin-stat-icon material-symbols-rounded">{icon}</span>',
                        unsafe_allow_html=True)
                    st.caption(t(f"admin.stat_{key}"))
                    st.markdown(f'<strong class="admin-stat-number">{value}</strong>', unsafe_allow_html=True)
                    st.caption(caption)
        manage_tab, audit_tab, runs_tab = st.tabs([
            t("admin.member_tab"), t("admin.audit"), t("admin.runs_label")])
        with manage_tab:
            edits = _member_editor(profiles, usage)
            _save_changes(edits)
        with audit_tab:
            _audit_history(profiles)
        with runs_tab:
            _recent_runs(profiles)
