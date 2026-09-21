"""Which models the app calls, and the keys they need — saved, not deployed.

`secrets.toml` is read once at startup and lives on the server's disk. That is
fine while someone can reach that disk; on a hosted deployment, changing a
model means editing a file and restarting, and finding out whether the new one
answers means starting a real run and waiting.

So the same shape as `search_sources`: a JSON file beside secrets.toml, read
through a lookup that falls back to `auth.setting`. A deployment that already
configures everything in the environment keeps working untouched, and nothing
written here has to be redeployed to take effect.

Two things this deliberately does not do:

* It will not shadow a setting outside `managed()`. The lookup is a whitelist,
  so no amount of typing on the settings page can redirect `SUPABASE_URL`,
  hand out `SUPABASE_SECRET_KEY`, or switch on `STORM_DEV_USER`.
* It keeps the keys out of the database, for the reason `search_sources` gives:
  the app reads Supabase as the signed-in member, so a key any member's session
  can read is a key any member can take.
"""

import json
import os
import time

import auth

SETTINGS_PATH = os.path.join(auth.state_dir(), "model_settings.json")

# The two model roles, and the per-role settings each one accepts.
ROLES = ("FAST", "STRONG")

# A prompt whose right answer is one word, so the reply says "the model is
# reachable and talking" without a token bill worth mentioning.
PROBE = "Reply with the single word: ready"

# A role is probed with the budget that role runs on, from
# demo_util.ROLE_TOKENS. This matters for a reasoning model, which spends
# part of its budget thinking before it writes anything: DeepSeek v4.1
# Flash took all 500 of the fast role's tokens on thought and returned an
# empty string. Probed at a larger budget it passes and then fails on
# every call of the actual run, which is the wrong way round for a test to
# be wrong. Unused budget is not billed.
#
# PROBE_TOKENS is the fallback for a probe with no role. At 64 an earlier
# version reported every healthy Gemini model as "replied with nothing".
PROBE_TOKENS = 1000


def managed():
    """Setting names this page is allowed to answer for.

    Derived from the provider table rather than listed again here, so a
    provider added to `demo_util.PROVIDERS` is configurable from the page
    without a second edit. Imported inside the function because `demo_util`
    imports this module: by the time anything calls this, both are loaded.
    """
    import demo_util

    names = {
        "LLM_PROVIDER",
        SECONDARY,
        "ENCODER_PROVIDER",
        "LLM_API_BASE",
        "LLM_API_KEY",
    }
    for role in ROLES:
        names.add(f"LLM_{role}_PROVIDER")
        names.add(f"LLM_{role}_MODEL")
        names.add(f"LLM_{role}_REASONING")
    names.update(provider["key"] for provider in demo_util.PROVIDERS.values())
    names.update(provider.get("base") for provider in demo_util.PROVIDERS.values())
    # Embeddings can sit on Azure even when no chat role does, and on an
    # Ollama this machine runs, which is addressed rather than keyed.
    names.update(("AZURE_API_KEY", "OLLAMA_API_BASE", "OLLAMA_EMBEDDING_MODEL"))
    names.discard(None)
    return names


def load():
    """Everything saved. Never leaves the server."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as handle:
            saved = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return saved if isinstance(saved, dict) else {}


def save(values):
    """Write the settings given. A blank value leaves the old one alone.

    Blank means "I did not retype the key", not "clear it" — the page shows a
    saved key as four characters, so an empty box is the normal state for a
    key that is already set. `forget` is how a value is removed.
    """
    merged = load()
    allowed = managed()
    for name, value in values.items():
        if name not in allowed:
            raise KeyError(f"{name} is not a setting this page manages")
        value = (value or "").strip()
        if value:
            merged[name] = value
    _write(merged)


def forget(name):
    """Drop one setting, falling back to the environment again."""
    saved = load()
    saved.pop(name, None)
    _write(saved)


def _write(values):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump(values, handle, indent=2)
    # Model keys, same as search_sources.json. Readable by the owner only.
    os.chmod(SETTINGS_PATH, 0o600)


# Not a setting name, so `save` refuses it and `setting` never returns it:
# the list of models a member may pick lives beside the settings, not among them.
PRESETS_KEY = "_presets"


# The second slot's provider. The first is LLM_PROVIDER, which predates
# this and is what a deployment configured through the environment sets.
SECONDARY = "LLM_SECONDARY_PROVIDER"

# Re-exported so the page does not have to import demo_util for one word.
REASONING_OFF = "off"


def provider_slots():
    """(primary, secondary) — the two providers this deployment uses.

    Two rather than a row per provider the app knows: a deployment uses one
    or two, and asking about five made the page mostly empty boxes. Which
    provider fills a slot is a choice; the key then belongs to that choice.

    `secondary` is None when unset, unusable, or the same as primary. An
    unnamed primary falls back to the only provider with a key — filling in
    one key says enough — and then to gemini, which is what the app has
    always defaulted to.
    """
    import demo_util

    primary = (setting("LLM_PROVIDER") or "").strip().lower()
    if primary not in demo_util.PROVIDERS:
        with_keys = [n for n, p in demo_util.PROVIDERS.items() if setting(p["key"])]
        primary = with_keys[0] if len(with_keys) == 1 else "gemini"

    secondary = (setting(SECONDARY) or "").strip().lower()
    if secondary not in demo_util.PROVIDERS or secondary == primary:
        secondary = None
    return primary, secondary


def configured_providers():
    """The slots that can actually be called, primary first.

    A key, and a base URL for the one provider that is an endpoint rather
    than a service. This is the list the pickers offer: choosing a provider
    with no key saves a setting that fails when a run starts, in front of
    whoever pressed the button rather than the admin who chose it.
    """
    import demo_util

    ready = []
    for name in provider_slots():
        if not name:
            continue
        provider = demo_util.PROVIDERS[name]
        if not setting(provider["key"]):
            continue
        if provider.get("base") and not setting(provider["base"]):
            continue
        ready.append(name)
    return ready


def default_provider():
    """The provider both roles use unless one names another."""
    primary, _ = provider_slots()
    ready = configured_providers()
    if primary in ready:
        return primary
    return ready[0] if ready else primary


def presets():
    """Models the admin has put on offer for the strong role, in order.

    Each is {"id", "label", "provider", "model"}. The id is what a run
    remembers; the label is what the picker shows. Only the strong role is
    offered — it is the one that writes, and the one a person has an
    opinion about. The fast role keeps the admin's choice.
    """
    saved = load().get(PRESETS_KEY, [])
    clean = []
    for entry in saved if isinstance(saved, list) else []:
        if not isinstance(entry, dict):
            continue
        if entry.get("id") and entry.get("provider") and entry.get("model"):
            clean.append(
                {
                    "id": str(entry["id"]),
                    "label": str(entry.get("label") or entry["model"]),
                    "provider": str(entry["provider"]).strip().lower(),
                    "model": str(entry["model"]).strip(),
                }
            )
    return clean


def set_presets(entries):
    """Replace the offered list. Ids are made from the label if missing."""
    import re

    current = load()
    clean = []
    seen = set()
    for entry in entries or []:
        provider = str(entry.get("provider") or "").strip().lower()
        model = str(entry.get("model") or "").strip()
        label = str(entry.get("label") or model).strip()
        if not (provider and model):
            continue
        base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "model"
        ident = base
        n = 2
        while ident in seen:
            ident = f"{base}-{n}"
            n += 1
        seen.add(ident)
        clean.append({"id": ident, "label": label, "provider": provider, "model": model})
    current[PRESETS_KEY] = clean
    _write(current)


def preset_lookup(preset_id):
    """A `lookup` for `demo_util.resolve_role` that answers the strong role
    from a preset and everything else from the saved settings.

    None when the id is unknown — a preset removed by the admin after
    someone picked it — so the run quietly uses the default rather than
    failing on a choice that no longer exists.
    """
    chosen = next((p for p in presets() if p["id"] == preset_id), None)
    if not chosen:
        return None

    def lookup(name):
        if name == "LLM_STRONG_PROVIDER":
            return chosen["provider"]
        if name == "LLM_STRONG_MODEL":
            return chosen["model"]
        return setting(name)

    return lookup


def setting(name):
    """A saved value, else whatever `auth.setting` finds.

    This is the lookup `demo_util` uses in place of `auth.setting`, so the
    resolution order becomes: saved on this page, then secrets.toml, then the
    environment.
    """
    if name in managed():
        saved = load().get(name)
        if saved:
            return saved
    return auth.setting(name)


def hint(name):
    """(is set, last four) for showing a key without showing it."""
    value = setting(name)
    if not value:
        return False, ""
    return True, str(value)[-4:]


def is_saved_here(name):
    """Whether the value in use came from this page rather than the server.

    Worth drawing differently: a key from the environment cannot be forgotten
    from here, and saying so is kinder than a button that does nothing.
    """
    return bool(load().get(name))


def check(role, overrides=None):
    """Call one role's model once. Returns a dict describing what happened.

    `thought` is how many tokens the model spent thinking before it answered,
    which is how the page knows whether this model has thinking to turn off.
    It is observed rather than looked up: no provider here publishes it per
    model in a way that covers all of them, and a catalogue would say what a
    model is capable of rather than what it just did.

    `overrides` lets a key or model be tried before it is saved, the way the
    search page tests a key. Caching is switched off for the call: a cached
    answer would prove the model replied once, which is not the question.
    """
    import demo_util

    overrides = {name: value for name, value in (overrides or {}).items() if value}

    def lookup(name):
        return overrides.get(name) or setting(name)

    def outcome(ok, message, seconds=0.0, reply="", thought=0):
        return {
            "ok": ok,
            "message": message,
            "seconds": seconds,
            "reply": reply,
            "thought": thought,
        }

    started = time.monotonic()
    try:
        default = (lookup("LLM_PROVIDER") or "gemini").strip().lower()
        model, kwargs = demo_util.resolve_role(role, default, lookup=lookup)
    except demo_util.LMConfigError as error:
        return outcome(False, str(error))
    try:
        budget = demo_util.ROLE_TOKENS.get(role, PROBE_TOKENS)
        lm = demo_util.build_lm(model, budget, kwargs)
        answers = lm(prompt=PROBE, cache=False)
    except Exception as error:  # noqa: BLE001 - any provider, any failure
        return outcome(
            False, f"{type(error).__name__}: {error}", time.monotonic() - started
        )
    elapsed = time.monotonic() - started
    thought = _thinking_tokens(lm)
    # A reasoning model that spends the whole budget thinking answers with a
    # list holding None, not with an empty string — `(answers[0] or "")`
    # rather than a bare index, or the page dies with an AttributeError
    # instead of reporting a model that said nothing.
    reply = ((answers[0] if answers else "") or "").strip()
    if not reply:
        # Reachable but silent, on the budget this role really runs with —
        # so the run would do the same. Usually a reasoning model with no
        # room left to answer in.
        return outcome(False, "empty_reply", elapsed, thought=thought)
    return outcome(True, model, elapsed, reply, thought)


def _thinking_tokens(lm):
    """Tokens the last call spent thinking, or 0 if it did not or cannot say.

    dspy keeps the provider's whole usage block on the call it just made;
    `log_usage` reduces it to prompt and completion totals and drops this.
    A provider that does not report the detail reads as 0, which is the same
    as not thinking — the switch stays hidden and the model is left alone.
    """
    history = getattr(lm, "history", None)
    if not history:
        return 0
    usage = history[-1].get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    try:
        return int(details.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _encoder_outcome(ok, message, seconds=0.0, dimensions=0):
    """One shape of result for both tests, so the page unpacks one thing."""
    return {
        "ok": ok,
        "message": message,
        "seconds": seconds,
        "reply": dimensions,
        "thought": 0,
    }


def check_encoder(overrides=None):
    """Embed one short string. Returns the same dict shape `check` does.

    `reply` carries the vector's width rather than a reply, and `thought` is
    always 0 — an embedding model has nothing to think about.

    Co-STORM needs embeddings and STORM does not, so this is a separate test:
    a deployment can be perfectly healthy for one engine and unusable for the
    other, and one green tick covering both would hide that.
    """
    import costorm

    overrides = {name: value for name, value in (overrides or {}).items() if value}
    saved_env = {}
    started = time.monotonic()
    try:
        name, key = costorm.encoder_settings(
            lookup=lambda setting_name: overrides.get(setting_name) or setting(setting_name)
        )
    except Exception as error:  # noqa: BLE001 - config errors carry their own text
        return _encoder_outcome(False, str(error))
    env_extra = {
        n: overrides.get(n) or setting(n)
        for n in costorm.OLLAMA_SETTINGS
        if overrides.get(n) or setting(n)
    }
    try:
        from knowledge_storm.encoder import Encoder

        # The encoder reads its own configuration from the environment, with
        # no way to hand one in, so the choice is published there and put back
        # afterwards rather than left changed for the rest of the process.
        published = {"ENCODER_API_TYPE": name, **env_extra}
        if key is not None:
            published[costorm.ENCODERS[name]] = key
        for variable, value in published.items():
            saved_env[variable] = os.environ.get(variable)
            os.environ[variable] = value
        vector = Encoder().encode(PROBE)
    except Exception as error:  # noqa: BLE001 - any provider, any failure
        return _encoder_outcome(
            False, f"{type(error).__name__}: {error}", time.monotonic() - started
        )
    finally:
        for variable, value in saved_env.items():
            if value is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = value
    elapsed = time.monotonic() - started
    size = len(vector[0]) if len(vector) and hasattr(vector[0], "__len__") else len(vector)
    return _encoder_outcome(True, name, elapsed, size)
