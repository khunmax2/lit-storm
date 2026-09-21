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
        # Wrapped: the part of a provider error that says what went wrong
        # is at the end, after the exception class and litellm's own
        # re-raise. Unwrapped it sits past the right edge of the card.
        st.code(
            t("models.empty_reply") if message == "empty_reply" else message,
            language=None,
            wrap_lines=True,
        )
        # A rejected key reads as a fault in this app rather than at the
        # provider: OpenRouter answers a revoked key with "User not found",
        # which sounds like a missing account here. Say whose it is.
        if message.startswith("AuthenticationError"):
            st.caption(t("models.auth_hint"))
        return
    if scope == "encoder":
        st.success(t("models.encoder_ok", seconds=f"{seconds:.1f}", dimensions=extra))
    else:
        st.success(t("models.test_ok", model=message, seconds=f"{seconds:.1f}", reply=extra))
    if seconds >= SLOW_SECONDS:
        st.warning(t("models.slow", seconds=f"{seconds:.0f}"))


def _provider_picker(label, key, current, allow_inherit):
    """A provider dropdown, offering only providers with a key saved.

    Streamlit cannot grey out one option of a selectbox, so a provider
    without a key is absent rather than dimmed. Nothing is hidden by that:
    the keys card above lists every provider the app knows, which is where
    you find out one exists and give it a key.
    """
    names = model_settings.configured_providers()
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


def _provider_slot(slot, chosen, other):
    """One of the two provider slots: which provider, and its key.

    `slot` is "primary" or "secondary"; `other` is what the opposite slot
    holds, so the same provider cannot be chosen twice.
    """
    known = [n for n in demo_util.PROVIDERS if n != other]
    options = ([""] if slot == "secondary" else []) + known
    if chosen not in options:
        chosen = options[0]

    ready = chosen in model_settings.configured_providers()
    with st.container(border=True, key=f"slot_{slot}"):
        state = (
            ui_theme.badge(t("models.key_ready"), tone="positive")
            if ready
            else ui_theme.badge(t("models.key_missing"), tone="warning")
        )
        st.markdown(
            f'<div class="src-head"><span class="name">{t(f"models.slot_{slot}")}</span>'
            f'<span class="tags">{state if chosen else ""}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(t(f"models.slot_{slot}_what"))

        provider = st.selectbox(
            t("models.provider"),
            options,
            index=options.index(chosen),
            key=f"slot_prov_{slot}",
            format_func=lambda name: t("models.slot_none") if name == "" else name,
        )
        if not provider:
            if st.button(t("models.save"), key=f"slot_save_{slot}", width="stretch"):
                model_settings.forget(model_settings.SECONDARY)
                st.rerun()
            return

        details = demo_util.PROVIDERS[provider]
        typed_key = _key_box(details["key"], f"slot_{slot}")
        typed_base = ""
        if details.get("base"):
            typed_base = st.text_input(
                t("models.api_base"),
                value=model_settings.setting(details["base"]) or "",
                key=f"slot_base_{slot}",
                placeholder="https://api.example.com/v1",
            )
        if st.button(t("models.save"), key=f"slot_save_{slot}", type="primary", width="stretch"):
            pending = {details["key"]: typed_key}
            if details.get("base"):
                pending[details["base"]] = typed_base
            model_settings.save({k: v for k, v in pending.items() if v})
            name = "LLM_PROVIDER" if slot == "primary" else model_settings.SECONDARY
            model_settings.save({name: provider})
            st.rerun()


def _provider_slots():
    """The two slots, side by side."""
    primary, secondary = model_settings.provider_slots()
    columns = st.columns(2, gap="medium")
    with columns[0]:
        _provider_slot("primary", primary, secondary)
    with columns[1]:
        _provider_slot("secondary", secondary or "", primary)


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
            # What suits this role differs enough between the two that
            # naming a good model for one is bad advice for the other.
            help=t(f"models.pick_{role.lower()}"),
        )
        if placeholder:
            st.caption(t("models.model_default", name=placeholder))
        elif not model:
            st.caption(t("models.model_no_default"))

        # No key box here. A key belongs to a provider, and every provider
        # the dropdown above offers already has one — the keys card is where
        # they are entered, once each.
        pending = {
            f"LLM_{role}_PROVIDER": provider,
            f"LLM_{role}_MODEL": model,
        }

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
    default = model_settings.default_provider()

    with st.container(border=True, key="role_encoder"):
        effective = current or default
        tone = "info" if effective in costorm.ENCODERS else "warning"
        st.markdown(
            f'<div class="src-head"><span class="name">{t("models.encoder")}</span>'
            f'<span class="tags">{ui_theme.badge(effective, tone=tone)}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(t("models.encoder_what"))

        # Embedding services that can be called: a key saved, or no key
        # needed at all. The chat pickers filter the same way and for the
        # same reason; the set differs because Azure sells embeddings here
        # without being a chat provider, and Ollama runs on this machine.
        usable = [
            name
            for name, key in costorm.ENCODERS.items()
            if key is None or model_settings.setting(key)
        ]
        options = [""] + sorted(usable)
        index = options.index(current) if current in options else 0
        provider = st.selectbox(
            t("models.provider"),
            options,
            index=index,
            key="prov_encoder",
            format_func=lambda name: t("models.inherit") if name == "" else name,
        )
        chosen = (provider or default).strip().lower()
        typed_key = ""
        typed_ollama = {}
        if chosen not in costorm.ENCODERS:
            st.warning(t("models.encoder_unavailable", name=chosen))
        elif costorm.ENCODERS[chosen] is None:
            # Addressed, not authenticated. Both boxes are optional: the
            # defaults are right for an Ollama on this machine, and the
            # placeholders say what they are.
            st.caption(t("models.ollama_what"))
            typed_ollama["OLLAMA_EMBEDDING_MODEL"] = st.text_input(
                t("models.model_name"),
                value=model_settings.setting("OLLAMA_EMBEDDING_MODEL") or "",
                key="encoder_ollama_model",
                placeholder="bge-m3:latest",
            )
            typed_ollama["OLLAMA_API_BASE"] = st.text_input(
                t("models.api_base"),
                value=model_settings.setting("OLLAMA_API_BASE") or "",
                key="encoder_ollama_base",
                placeholder="http://localhost:11434",
            )
        else:
            typed_key = _key_box(costorm.ENCODERS[chosen], "encoder")

        pending = {"ENCODER_PROVIDER": provider, **typed_ollama}
        if costorm.ENCODERS.get(chosen):
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

    # Changing the default provider leaves the role model names behind —
    # they are ids in the old provider's vocabulary, or absent for a provider
    # that ships no defaults. Both fail when a run starts, in front of
    # whoever pressed the button rather than the admin who changed this. So
    # resolve them here and say so now.
    try:
        demo_util.lm_settings()
    except demo_util.LMConfigError as error:
        st.error(t("models.cannot_run"))
        st.code(str(error), language=None, wrap_lines=True)

    _provider_slots()

    if not model_settings.configured_providers():
        st.info(t("models.no_keys"))
        return

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
            provider = st.selectbox(t("models.provider"),
                                    model_settings.configured_providers(),
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
