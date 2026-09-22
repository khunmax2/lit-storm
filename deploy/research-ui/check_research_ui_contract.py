"""Report how far a Deep Research checkout is from what this repo expects.

Reads research-ui-pin.json and compares it against a checkout of the fork.
It reports; it does not force a move. Every rebase of the fork onto upstream
is a decision taken with the diff in front of you, not something a script
does on the way to a deploy.

    python deploy/research-ui/check_research_ui_contract.py ../deep-research-web-ui

Exit 0 when the checkout is at the pinned commit, 1 when it has moved, 2
when it cannot be read. Also checks the two locale files still share their
keys, since a Thai string missing is a Chinese one showing — the fallback
locale is zh.
"""

import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
PIN = json.loads((HERE / "research-ui-pin.json").read_text(encoding="utf-8"))


def git(checkout, *args):
    result = subprocess.run(
        ["git", "-C", str(checkout), *args], capture_output=True, text=True
    )
    if result.returncode:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def locale_keys(path):
    def walk(node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from walk(value, prefix + key + ".")
            else:
                yield prefix + key

    return set(walk(json.loads(path.read_text(encoding="utf-8"))))


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    checkout = pathlib.Path(sys.argv[1]).resolve()
    if not (checkout / ".git").exists():
        print(f"{checkout} is not a git checkout")
        return 2

    head = git(checkout, "rev-parse", "--short", "HEAD")
    pinned = PIN["fork"]["commit"]
    status = 0

    if head.startswith(pinned) or pinned.startswith(head):
        print(f"fork: at pinned {pinned}")
    else:
        ahead = git(checkout, "rev-list", "--count", f"{pinned}..HEAD")
        behind = git(checkout, "rev-list", "--count", f"HEAD..{pinned}")
        print(f"fork: HEAD {head} is {ahead} ahead / {behind} behind pinned {pinned}")
        status = 1

    upstream = PIN["upstream"]["commit"]
    try:
        distance = git(checkout, "rev-list", "--count", f"{upstream}..HEAD")
        print(f"upstream: {distance} fork commit(s) on top of {upstream}")
    except SystemExit as error:
        print(f"upstream: {upstream} not reachable from HEAD — {error}")
        status = max(status, 1)

    en = locale_keys(checkout / "i18n" / "en.json")
    th_path = checkout / "i18n" / "th.json"
    if th_path.exists():
        th = locale_keys(th_path)
        missing = sorted(en - th)
        extra = sorted(th - en)
        if missing or extra:
            print(f"locale: th.json missing {len(missing)}, extra {len(extra)}")
            for key in missing[:10]:
                print(f"  missing: {key}")
            status = max(status, 1)
        else:
            print(f"locale: th.json level with en.json ({len(en)} keys)")
    else:
        print("locale: th.json is absent")
        status = max(status, 1)

    # The locale list lives in more than one place, and only some of them are
    # the UI. The first build that added Thai updated nuxt.config.ts and the
    # i18n config and shipped — then every research request came back 400,
    # because the server's zod schema had its own copy of the list. So:
    # every copy must name every locale the UI offers.
    ui = set(re.findall(r"'([a-z]{2})'", re.search(
        r"locales:\s*\[([^\]]*)\]", (checkout / "nuxt.config.ts").read_text(encoding="utf-8")
    ).group(1)))
    copies = {
        "shared/utils/research-input.ts": r"SUPPORTED_LOCALES\s*=\s*\[([^\]]*)\]",
        "i18n/i18n.config.ts": r"availableLocales:\s*\[([^\]]*)\]",
        "lib/prompt.ts": r"LANGUAGE_NAMES[^{]*\{([^}]*)\}",
    }
    for rel, pattern in copies.items():
        text = (checkout / rel).read_text(encoding="utf-8")
        found = re.search(pattern, text)
        # Two shapes: a quoted list ('en', 'zh') or an object's keys (en: …).
        listed = (
            set(re.findall(r"'([a-z]{2})'", found.group(1)))
            | set(re.findall(r"^\s*([a-z]{2}):", found.group(1), re.M))
        ) if found else set()
        missing = sorted(ui - listed)
        if missing:
            print(f"locale: {rel} lacks {', '.join(missing)} that the UI offers")
            status = max(status, 1)
    if status == 0:
        print(f"locale: every copy of the list names all of {', '.join(sorted(ui))}")

    for param in PIN["verified_against"]["frame_params"]:
        source = (checkout / "app" / "composables" / "useEmbed.ts")
        if not source.exists() or f"'{param}'" not in source.read_text(encoding="utf-8"):
            if not source.exists() or f"query.{param}" not in source.read_text(encoding="utf-8"):
                print(f"frame: ?{param} is not read by useEmbed.ts")
                status = max(status, 1)

    # The one thing we read that is not an interface the sibling offers: its
    # own history, out of the localStorage both applications share because
    # the proxy gives them one origin. That is a borrowed internal, and the
    # price of borrowing it is saying so here. A rebase that renames the key
    # or drops a field we file reports by should fail this script, not go
    # quiet until somebody notices nothing has reached their library.
    storage = PIN["verified_against"].get("history_storage")
    if storage:
        sources = [
            path
            for path in checkout.rglob("*.ts")
            if "node_modules" not in path.parts and ".output" not in path.parts
        ] + [
            path
            for path in checkout.rglob("*.vue")
            if "node_modules" not in path.parts and ".output" not in path.parts
        ]
        holders = [
            path
            for path in sources
            if storage["key"] in path.read_text(encoding="utf-8", errors="ignore")
        ]
        if not holders:
            print(f"history: no source names {storage['key']} — the sync reads nothing")
            status = max(status, 1)
        else:
            where = ", ".join(
                str(path.relative_to(checkout)) for path in holders[:3]
            )
            text = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore") for path in holders
            )
            missing = [f for f in storage["item_fields"] if f not in text]
            if missing:
                print(
                    f"history: {where} no longer mentions {', '.join(missing)} — "
                    "reports would sync without them"
                )
                status = max(status, 1)
            else:
                print(f"history: {storage['key']} and its fields still in {where}")

    if PIN["image"].get("digest") is None:
        print("image: no digest published — local build only; a deploy must not proceed on this")

    return status


if __name__ == "__main__":
    sys.exit(main())
