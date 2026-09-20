"""The sign-in gate and the account block in the sidebar."""

import auth
from html import escape
import streamlit as st
import ui_theme
from ui_language import t
from member_management import MemberManagementError

MIN_PASSWORD = 8


def _report_provider_error(error):
    st.error(t("auth.failed"))
    with st.expander(t("create.failed_detail")):
        st.code(f"{type(error).__name__}: {error}", language=None)


def _sign_in_form():
    with st.form("signin"):
        email = st.text_input(t("auth.email"), key="signin_email")
        password = st.text_input(
            t("auth.password"), type="password", key="signin_password"
        )
        submitted = st.form_submit_button(
            t("auth.do_signin"), type="primary", width="stretch"
        )
    if not submitted:
        return
    if not email or not password:
        st.warning(t("auth.needs_fields"), icon=":material/warning:")
        return
    try:
        auth.sign_in(email.strip(), password)
    except Exception as error:  # noqa: BLE001 - the provider's message varies
        _report_provider_error(error)
        return
    st.rerun()


def _sign_up_form():
    with st.form("signup"):
        name = st.text_input(t("auth.name"), key="signup_name")
        email = st.text_input(t("auth.email"), key="signup_email")
        password = st.text_input(
            t("auth.password"), type="password", key="signup_password"
        )
        submitted = st.form_submit_button(
            t("auth.do_signup"), type="primary", width="stretch"
        )
    if not submitted:
        return
    if not email or not password:
        st.warning(t("auth.needs_fields"), icon=":material/warning:")
        return
    if len(password) < MIN_PASSWORD:
        st.warning(t("auth.password_short"), icon=":material/warning:")
        return
    try:
        result = auth.sign_up(email.strip(), password, name.strip() or None)
    except MemberManagementError as error:
        st.warning(t(f"admin.error_{error}"), icon=":material/warning:")
        return
    except Exception as error:  # noqa: BLE001 - the provider's message varies
        _report_provider_error(error)
        return
    if result.session:
        st.rerun()
    else:
        # Supabase returns a user without a session when e-mail confirmation
        # is switched on for the project.
        st.success(t("auth.check_email"))


def gate():
    """Draw the sign-in screen. Returns True when the caller may continue."""
    if auth.signed_in():
        current = auth.profile(refresh=True)
        if not current:
            st.error(t("auth.no_profile"))
        elif current.get("is_active", True):
            return True
        else:
            st.error(t("auth.suspended"))
        if st.button(t("auth.signout"), key="signin_suspended_signout"):
            auth.sign_out()
            st.rerun()
        return False

    ui_theme.hero(
        eyebrow=t("create.eyebrow"),
        title=t("auth.title"),
        subtitle=t("auth.subtitle"),
    )

    if not auth.configured():
        _, middle, _ = st.columns([1, 3, 1])
        with middle:
            st.error(t("auth.not_configured"))
        return False

    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        sign_in_tab, sign_up_tab = st.tabs(
            [t("auth.tab_signin"), t("auth.tab_signup")]
        )
        with sign_in_tab:
            _sign_in_form()
        with sign_up_tab:
            _sign_up_form()
    return False


def sidebar_account():
    """Who is signed in, what they may still spend, and the way out.

    Drawn after the navigation and pushed to the foot of the rail: it is who
    you are, not where you are going, and it should not sit between the brand
    and the menu.
    """
    with st.sidebar.container(key="side_account"):
        profile = auth.profile()
        if profile is None:
            st.warning(t("auth.no_profile"))
        else:
            role_label = (
                t("auth.role_admin") if auth.is_admin() else t("auth.role_member")
            )
            used, limit = auth.quota()
            name = auth.display_name()
            st.markdown(
                f'<div class="side-account">'
                f'<span class="avatar">{escape(name.strip()[:1].upper())}</span>'
                f'<span class="who"><span class="name">{escape(name)}</span>'
                f'<span class="meta">{escape(role_label)}'
                f'<span class="sep"> · </span>'
                f'{escape(t("auth.quota", used=used, limit=limit))}</span></span></div>',
                unsafe_allow_html=True,
            )
        if st.button(
            t("auth.signout"),
            icon=":material/logout:",
            type="tertiary",
            width="stretch",
        ):
            auth.sign_out()
            st.rerun()
