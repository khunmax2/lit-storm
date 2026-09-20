"""Which models the app calls — an admin's page.

The shape follows the search sources page on purpose: a card per thing that
can be configured, a key that can be tested before it is saved, and a saved
key shown as four characters rather than sent back to the browser.

What it adds is timing. A model that answers in forty seconds is not broken
and will not raise anything — it will just make every run unbearable, and the
only way to find out today is to start a fifteen-minute discussion. The test
reports how long the answer took, so a bad alias is visible in one click.
"""

import auth
import costorm
import demo_util
import model_settings
import streamlit as st
import ui_theme
from ui_language import t

TEST_RESULT = "page6_model_test"

# Anything slower than this on a one-word prompt is a problem worth naming.
# `gemini-flash-latest` resolving to a 30-57s model is the case in mind; the
# healthy providers answered the same prompt in one to eight seconds.
SLOW_SECONDS = 15.0


def _remember(scope, outcome):
    st.session_state[TEST_RESULT] = (scope, *outcome)


def _show_test(scope):
    result = st.session_state.get(TEST_RESULT)
    if not result or result[0] != scope:
        return
    _, ok, message, seconds, extra = result
    if not ok:
        st.error(t("models.test_failed"))
        st.code(t("models.empty_reply") if message == "empty_reply" else message, language=None)
        return
    if scope == "encoder":
        st.success(t("models.encoder_ok", seconds=f"{seconds:.1f}", dimensions=extra))
    else:
        st.success(t("models.test_ok", model=message, seconds=f"{seconds:.1f}", reply=extra))
    if seconds >= SLOW_SECONDS:
        st.warning(t("models.slow", seconds=f"{seconds:.0f}"))


def _provider_picker(label, key, current, allow_inherit):
    """A provider dropdown. `allow_inherit` adds "same as the default"."""
    names = sorted(demo_util.PROVIDERS)
    options = ([""] if allow_inherit else []) + names
    index = options.index(current) if current in options else 0
    return st.selectbox(
        label,
        options,
        index=index,
        key=key,
        format_func=lambda name: t("models.inherit") if name == "" else name,
    )


def _key_box(key_name, prefix):
    """A password box for one provider key, labelled by what is already set."""
    is_set, last4 = model_settings.hint(key_name)
    label = (
        t("models.key_saved", name=key_name, last4=last4)
        if is_set
        else t("models.key_needed", name=key_name)
    )
    typed = st.text_input(
        label,
        type="password",
        key=f"{prefix}_{key_name}",
        placeholder="•" * 12 if is_set else "",
    )
    if is_set and not typed and model_settings.is_saved_here(key_name):
        if st.button(t("models.forget_key"), key=f"forget_{prefix}_{key_name}", type="tertiary"):
            model_settings.forget(key_name)
            st.rerun()
    elif is_set and not model_settings.is_saved_here(key_name):
        st.caption(t("models.from_server"))
    return typed


def _role_card(role):
    """One of the two model roles: provider, model name, key, test, save."""
    saved_provider = (model_settings.setting(f"LLM_{role}_PROVIDER") or "").strip().lower()
    default_provider = (model_settings.setting("LLM_PROVIDER") or "gemini").strip().lower()
    effective = saved_provider or default_provider

    with st.container(border=True, key=f"role_{role}"):
        st.markdown(
            f'<div class="src-head"><span class="name">{t(f"models.role_{role.lower()}")}</span>'
            f'<span class="tags">{ui_theme.badge(effective, tone="info")}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(t(f"models.role_{role.lower()}_what"))

        provider = _provider_picker(
            t("models.provider"), f"prov_{role}", saved_provider, allow_inherit=True
        )
        chosen = (provider or default_provider).strip().lower()
        details = demo_util.PROVIDERS.get(chosen, {})

        placeholder = details.get(role.lower()) or ""
        model = st.text_input(
            t("models.model_name"),
            value=model_settings.setting(f"LLM_{role}_MODEL") or "",
            key=f"model_{role}",
            placeholder=placeholder or t("models.model_required"),
        )
        if placeholder:
            st.caption(t("models.model_default", name=placeholder))
        elif not model:
            st.caption(t("models.model_no_default"))

        typed_key = _key_box(details.get("key", ""), f"role_{role}") if details.get("key") else ""
        typed_base = ""
        if details.get("base"):
            typed_base = st.text_input(
                t("models.api_base"),
                value=model_settings.setting(details["base"]) or "",
                key=f"base_{role}",
                placeholder="https://api.example.com/v1",
            )

        pending = {
            f"LLM_{role}_PROVIDER": provider,
            f"LLM_{role}_MODEL": model,
        }
        if details.get("key"):
            pending[details["key"]] = typed_key
        if details.get("base"):
            pending[details["base"]] = typed_base

        left, right = st.columns(2)
        with left:
            if st.button(
                t("models.test"), key=f"test_{role}", icon=":material/wifi_tethering:", width="stretch"
            ):
                with st.spinner(t("models.testing")):
                    _remember(role, model_settings.check(role, overrides=pending))
        with right:
            if st.button(t("models.save"), key=f"save_{role}", type="primary", width="stretch"):
                # A provider box left on "same as the default" is a real
                # choice, not a blank: it has to clear any saved override
                # rather than be skipped the way an untyped key is.
                if not provider:
                    model_settings.forget(f"LLM_{role}_PROVIDER")
                if not model:
                    model_settings.forget(f"LLM_{role}_MODEL")
                model_settings.save({k: v for k, v in pending.items() if v})
                st.rerun()

        _show_test(role)


def _encoder_card():
    """Embeddings, which only Co-STORM needs and only some providers sell."""
    current = (model_settings.setting("ENCODER_PROVIDER") or "").strip().lower()
    default = (model_settings.setting("LLM_PROVIDER") or "gemini").strip().lower()

    with st.container(border=True, key="role_encoder"):
        effective = current or default
        tone = "info" if effective in costorm.ENCODERS else "warning"
        st.markdown(
            f'<div class="src-head"><span class="name">{t("models.encoder")}</span>'
            f'<span class="tags">{ui_theme.badge(effective, tone=tone)}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(t("models.encoder_what"))

        options = [""] + sorted(costorm.ENCODERS)
        index = options.index(current) if current in options else 0
        provider = st.selectbox(
            t("models.provider"),
            options,
            index=index,
            key="prov_encoder",
            format_func=lambda name: t("models.inherit") if name == "" else name,
        )
        chosen = (provider or default).strip().lower()
        if chosen not in costorm.ENCODERS:
            st.warning(t("models.encoder_unavailable", name=chosen))
            typed_key = ""
        else:
            typed_key = _key_box(costorm.ENCODERS[chosen], "encoder")

        pending = {"ENCODER_PROVIDER": provider}
        if chosen in costorm.ENCODERS:
            pending[costorm.ENCODERS[chosen]] = typed_key

        left, right = st.columns(2)
        with left:
            if st.button(
                t("models.test"), key="test_encoder", icon=":material/wifi_tethering:", width="stretch"
            ):
                with st.spinner(t("models.testing")):
                    _remember("encoder", model_settings.check_encoder(overrides=pending))
        with right:
            if st.button(t("models.save"), key="save_encoder", type="primary", width="stretch"):
                if not provider:
                    model_settings.forget("ENCODER_PROVIDER")
                model_settings.save({k: v for k, v in pending.items() if v})
                st.rerun()

        _show_test("encoder")


def model_settings_page():
    if not auth.is_admin():
        st.error(t("admin.not_admin"))
        return

    default = (model_settings.setting("LLM_PROVIDER") or "gemini").strip().lower()
    ui_theme.page_header(t("models.title"), t("models.using", name=default))
    st.caption(t("models.intro"))

    with st.container(border=True, key="role_default"):
        st.markdown(
            f'<div class="src-head"><span class="name">{t("models.default_provider")}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(t("models.default_what"))
        provider = _provider_picker(
            t("models.provider"), "prov_default", default, allow_inherit=False
        )
        details = demo_util.PROVIDERS.get(provider, {})
        typed_key = _key_box(details["key"], "default") if details.get("key") else ""
        typed_base = ""
        if details.get("base"):
            typed_base = st.text_input(
                t("models.api_base"),
                value=model_settings.setting(details["base"]) or "",
                key="base_default",
                placeholder="https://api.example.com/v1",
            )
        if st.button(t("models.save"), key="save_default", type="primary"):
            pending = {"LLM_PROVIDER": provider}
            if details.get("key"):
                pending[details["key"]] = typed_key
            if details.get("base"):
                pending[details["base"]] = typed_base
            model_settings.save({k: v for k, v in pending.items() if v})
            st.rerun()

    columns = st.columns(2, gap="medium")
    for column, role in zip(columns, model_settings.ROLES):
        with column:
            _role_card(role)

    _encoder_card()
    _presets_card()

    st.caption(t("models.where_saved"))


def _presets_card():
    """Models a member may pick for the strong role, one run at a time.

    The default stays whatever the cards above say; these are the
    alternatives on offer. A preset is a label, a provider and a model name
    — the provider's key comes from the settings above, so a preset on a
    provider with no key saved will fail the same way any run on it would,
    and the admin is the one who sees that, on Test, before offering it.
    """
    presets = model_settings.presets()
    with st.container(border=True, key="role_presets"):
        st.markdown(
            f'<div class="src-head"><span class="name">{t("models.presets")}</span>'
            f'<span class="tags">{ui_theme.badge(str(len(presets)), tone="info")}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(t("models.presets_what"))

        for index, preset in enumerate(presets):
            row, remove = st.columns([5, 1], vertical_alignment="center")
            with row:
                st.markdown(
                    f"**{preset['label']}** — `{preset['provider']}` · `{preset['model']}`"
                )
            with remove:
                if st.button(
                    t("models.preset_remove"),
                    key=f"preset_rm_{preset['id']}",
                    type="tertiary",
                    icon=":material/delete:",
                ):
                    model_settings.set_presets(presets[:index] + presets[index + 1 :])
                    st.rerun()

        st.markdown(f"**{t('models.preset_add')}**")
        label_col, provider_col, model_col = st.columns([2, 1.4, 2])
        with label_col:
            label = st.text_input(t("models.preset_label"), key="preset_new_label",
                                  placeholder="Pathumma LLM 27B")
        with provider_col:
            provider = st.selectbox(t("models.provider"), sorted(demo_util.PROVIDERS),
                                    key="preset_new_provider")
        with model_col:
            model = st.text_input(t("models.model_name"), key="preset_new_model",
                                  placeholder=demo_util.PROVIDERS[provider].get("strong") or "")
        left, right = st.columns(2)
        with left:
            if st.button(t("models.test"), key="preset_new_test",
                         icon=":material/wifi_tethering:", width="stretch"):
                with st.spinner(t("models.testing")):
                    _remember("preset_new", model_settings.check("STRONG", overrides={
                        "LLM_STRONG_PROVIDER": provider, "LLM_STRONG_MODEL": model,
                    }))
        with right:
            if st.button(t("models.preset_save"), key="preset_new_save", type="primary",
                         width="stretch", disabled=not model):
                model_settings.set_presets(presets + [{
                    "label": label or model, "provider": provider, "model": model,
                }])
                for key in ("preset_new_label", "preset_new_model"):
                    st.session_state.pop(key, None)
                st.rerun()
        _show_test("preset_new")
