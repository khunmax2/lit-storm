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

    for param in PIN["verified_against"]["frame_params"]:
        source = (checkout / "app" / "composables" / "useEmbed.ts")
        if not source.exists() or f"'{param}'" not in source.read_text(encoding="utf-8"):
            if not source.exists() or f"query.{param}" not in source.read_text(encoding="utf-8"):
                print(f"frame: ?{param} is not read by useEmbed.ts")
                status = max(status, 1)

    if PIN["image"].get("digest") is None:
        print("image: no digest published — local build only; a deploy must not proceed on this")

    return status


if __name__ == "__main__":
    sys.exit(main())
