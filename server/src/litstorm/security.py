"""Passwords, tokens and credentials at rest."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from litstorm import settings

_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 10


class WeakPassword(ValueError):
    pass


def hash_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(f"at least {MIN_PASSWORD_LENGTH} characters")
    return _hasher.hash(password)


def verify_password(password_hash, password):
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_token():
    """A random token for a URL or a cookie, and the hash to store instead."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token):
    # Tokens are long and random, so a fast hash is enough; what matters is
    # that the database never holds a usable token.
    return hashlib.sha256(token.encode()).hexdigest()


def same(a, b):
    return hmac.compare_digest(a or "", b or "")


class CredentialKeyMissing(RuntimeError):
    pass


def _fernet():
    key = settings.get().secret_key
    if not key:
        raise CredentialKeyMissing("LITSTORM_SECRET_KEY_FILE is not set")
    return Fernet(key)


def encrypt(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt(ciphertext):
    """The stored credential, or "" when the key it was sealed with is gone."""
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ""


def hint(value):
    """What an admin is shown of a stored key: its last four characters."""
    return f"…{value[-4:]}" if value else ""
