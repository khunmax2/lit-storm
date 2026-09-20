"""Validation shared by member widgets and server-side account operations."""

import re

ROLES = ("member", "admin")
EDITABLE = ("role", "monthly_run_limit", "is_active")
MAX_LIMIT = 2_147_483_647


class MemberManagementError(ValueError):
    """A safe, translatable error code; never carries passwords or API keys."""


def validate_account(email, password, display_name):
    email = email.strip().lower()
    name = (display_name or "").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise MemberManagementError("invalid_email")
    if len(password) < 8:
        raise MemberManagementError("password_short")
    if len(name) > 200:
        raise MemberManagementError("name_long")
    return email, password, name or email.split("@")[0]


def validate_changes(target, actor, fields):
    if set(fields) - set(EDITABLE):
        raise MemberManagementError("invalid_fields")
    if "role" in fields and fields["role"] not in ROLES:
        raise MemberManagementError("invalid_role")
    if "is_active" in fields and type(fields["is_active"]) is not bool:
        raise MemberManagementError("invalid_status")
    if "monthly_run_limit" in fields:
        limit = fields["monthly_run_limit"]
        if type(limit) is not int or not 0 <= limit <= MAX_LIMIT:
            raise MemberManagementError("invalid_limit")
    if target == actor and (
        fields.get("role", "admin") != "admin" or fields.get("is_active") is False
    ):
        raise MemberManagementError("self_protected")
    return fields


def pending_edits(originals, candidates, actor):
    """Validate the entire batch before any write, with optimistic baselines."""
    by_id = {row["id"]: row for row in originals}
    updates = []
    for candidate in candidates:
        target = candidate["id"]
        original = by_id.get(target)
        if original is None:
            raise MemberManagementError("missing_member")
        fields = {key: candidate[key] for key in EDITABLE if candidate[key] != original[key]}
        validate_changes(target, actor, fields)
        if fields:
            updates.append({
                "target": target,
                "changes": fields,
                "expected": {key: original[key] for key in EDITABLE},
            })
    return updates
