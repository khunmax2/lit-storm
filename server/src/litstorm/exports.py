"""Download links for a finished report's files, made for MCP clients
(research_export): an agent that cannot sign in to the web app fetches the
file with a plain GET, and a person can open the same link.

A link carries its own permission: the Run, the format, the Run's owner and
when it stops working, signed with the server's secret key (HMAC-SHA256).
Whoever has the link can fetch that one file until it expires, and nothing
else. Using it checks again that the Run is still its owner's and has its
report (api/research.py, /api/exports/{token}).
"""

import base64
import hashlib
import hmac
import json
import time

from litstorm import settings

FORMATS = ("interactive", "html", "md", "pdf", "observatory")
EXTENSIONS = {"interactive": "html", "html": "html", "md": "md", "pdf": "pdf", "observatory": "observatory.html"}
LIFETIME = 15 * 60  # seconds


class Invalid(Exception):
    """Not a link this server made, or tampered with."""


class Expired(Exception):
    """A real link, past its time."""


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key():
    secret = settings.get().secret_key
    if not secret:
        raise RuntimeError("LITSTORM_SECRET_KEY_FILE is not set")
    # A key of its own, derived from the server's, so a link's signature can
    # never stand in for anything else the secret key protects.
    return hashlib.sha256(b"litstorm-export-link:" + secret.encode()).digest()


def sign(run_id, user_id, fmt, now=None):
    """(token, expires_at) for one file of one Run."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt}")
    expires = int((now or time.time()) + LIFETIME)
    payload = _b64(json.dumps({"r": str(run_id), "u": str(user_id), "f": fmt, "e": expires},
                              separators=(",", ":")).encode())
    signature = _b64(hmac.new(_key(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}", expires


def verify(token, now=None):
    """The link's {run_id, user_id, format, expires}. Raises Invalid or Expired."""
    try:
        payload, signature = token.split(".")
        expected = _b64(hmac.new(_key(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise Invalid()
        data = json.loads(_unb64(payload))
        fact = {"run_id": data["r"], "user_id": data["u"], "format": data["f"], "expires": int(data["e"])}
    except (ValueError, KeyError, TypeError) as error:
        raise Invalid() from error
    if fact["format"] not in FORMATS:
        raise Invalid()
    if fact["expires"] <= (now or time.time()):
        raise Expired()
    return fact
