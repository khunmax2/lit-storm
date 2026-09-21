"""The applications this one frames, and how to tell whether they are up.

Two of the four engines are not this app's: Deep Research and the agents
researcher each run in their own container, coupled to this one by a URL and
nothing else — the shape ADR-0005 settled on. What they have in common lives
here so the two tabs cannot drift apart.

Each sibling has two addresses, and the difference matters:

* the **browser** address, which goes into the iframe and is resolved by the
  person's browser — `http://localhost:3100`, published by the compose file;
* the **internal** address, which this app uses to ask whether the sibling is
  up — `http://research-ui:3000`, the service name on the stack's network.

Probing the browser address from inside this container asks the container
about itself and always fails. That is not a hypothetical: it is the first
thing that goes wrong when a health check is added to a framed tab.
"""

import urllib.error
import urllib.request
from urllib.parse import urlencode

import auth
import streamlit as st
import ui_language

# The frame's language codes for this app's language names.
LANG_CODES = {"English": "en", "ไทย": "th"}

# A pixel height is what st.iframe actually honours: "stretch" fills the
# parent, and the parent here has no height of its own, so the frame came out
# at 180px with the page empty beneath it. The CSS in ui_theme raises this to
# the viewport's remaining height; this is the floor it falls back to.
FRAME_HEIGHT = 900


class Sibling:
    """One framed application: where it is, and what to call it."""

    def __init__(self, name, browser_setting, browser_default, internal_setting,
                 internal_default, health_path):
        self.name = name
        self.browser_setting = browser_setting
        self.browser_default = browser_default
        self.internal_setting = internal_setting
        self.internal_default = internal_default
        self.health_path = health_path

    def browser_url(self):
        return (auth.setting(self.browser_setting) or self.browser_default).strip().rstrip("/")

    def internal_url(self):
        return (auth.setting(self.internal_setting) or self.internal_default).strip().rstrip("/")


RESEARCH_UI = Sibling(
    name="research_ui",
    browser_setting="RESEARCH_UI_URL",
    browser_default="http://localhost:3100",
    internal_setting="RESEARCH_UI_INTERNAL_URL",
    internal_default="http://research-ui:3000",
    # Nuxt has no health endpoint of its own; the root answering 200 is the
    # same thing its container healthcheck asks for.
    health_path="/",
)

AGENTS_RESEARCH = Sibling(
    name="agents_research",
    browser_setting="AGENTS_RESEARCH_URL",
    browser_default="http://localhost:3200",
    internal_setting="AGENTS_RESEARCH_INTERNAL_URL",
    internal_default="http://agents-research:3000",
    # Ours, so it has a real one — and it reports whether a model key is
    # present as well as whether the process is up.
    health_path="/healthz",
)


@st.cache_data(ttl=15, show_spinner=False)
def _probe(url):
    """(reachable, detail) for one address. Cached: this runs on every rerun.

    Fifteen seconds is short enough that starting the container and switching
    back reads as immediate, and long enough that typing in a box does not
    open a socket per keystroke.
    """
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status < 400, str(response.status)
    except urllib.error.HTTPError as error:
        # Answering at all means the process is up; a 404 on the health path
        # is a wrong path, not a dead sibling.
        return error.code < 500, str(error.code)
    except Exception as error:  # noqa: BLE001 - refused, DNS, timeout
        return False, type(error).__name__


def reachable(sibling):
    """Whether the sibling answers at either address it might have.

    Both are tried because this app runs in two places. Inside the stack the
    service name resolves and the published port does not; on a laptop
    running `streamlit run` against the same containers it is the other way
    round — `agents-research:3000` is a Docker network name and means nothing
    on the host.

    Checking only the internal one was the first version, and it reported
    every sibling as down for anyone not running the app in a container.
    """
    tried = []
    for base in (sibling.internal_url(), sibling.browser_url()):
        if not base or base in [address for address, _ in tried]:
            continue
        ok, detail = _probe(base + sibling.health_path)
        if ok:
            return True, f"{base} → {detail}"
        tried.append((base, detail))

    if not tried:
        return False, "no address set"
    return False, ", ".join(f"{address} → {detail}" for address, detail in tried)


def frame_url(sibling):
    """The address the iframe loads, with the three parameters both honour.

    `lang` and `theme` so the frame matches the page around it, `embed=1` so
    it hides its own language and theme controls — which would otherwise sit
    under this app's and announce a second application.
    """
    base = sibling.browser_url()
    if not base:
        return ""
    theme = "light"
    try:
        theme = "dark" if st.context.theme.type == "dark" else "light"
    except Exception:  # noqa: BLE001 - no theme context outside a real session
        pass
    query = urlencode(
        {
            "embed": "1",
            "lang": LANG_CODES.get(ui_language.current(), "en"),
            "theme": theme,
        }
    )
    return f"{base}/?{query}"
