"""Task 8 of the 2026-10-24 audit: the translation check, a script (not a pytest test, on purpose:
the permanent suite stays free of tests that parse the web source).

    cd server && uv run python tests/audit/i18n_check.py

Reports, from web/src/i18n.tsx and the .tsx screens:
  1. en/th key parity (both directions) and keys whose Thai text is identical to the English one;
  2. server error codes (HTTPException(status, "code")) with no `error.<code>` key, which the
     screens show as the generic "Something went wrong";
  3. hard-coded user-visible strings in .tsx that do not go through t(): JSX text, and the
     placeholder / title / aria-label / alt / label attributes and toast calls with a literal.
     A heuristic: a candidate list, to be confirmed by reading.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "web/src"
SERVER = ROOT / "server/src/litstorm"

KEY = re.compile(r'^\s*(?:"([^"]+)"|([A-Za-z_][\w]*))\s*:\s*(?:"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)', re.M)


def dictionaries():
    src = (WEB / "i18n.tsx").read_text(encoding="utf-8")
    a = src.index("const en = {")
    b = src.index("export type Key")
    c = src.index("const th: Record<Key, string> = {")
    d = src.index("const dictionaries")
    out = []
    for chunk in (src[a:b], src[c:d]):
        out.append({m.group(1) or m.group(2): (m.group(3) if m.group(3) is not None else m.group(4)) for m in KEY.finditer(chunk)})
    return out


def parity():
    en, th = dictionaries()
    print(f"== 1. parity: en {len(en)} keys, th {len(th)} keys")
    print("   only in en:", sorted(set(en) - set(th)) or "none")
    print("   only in th:", sorted(set(th) - set(en)) or "none")
    same = [k for k in en if k in th and en[k] == th[k] and re.search(r"[A-Za-z]{4,}", en[k])]
    print(f"   th text identical to en (>=4 letters; names/terms may be intended): {len(same)}")
    for k in same:
        print(f"     {k} = {en[k][:70]!r}")
    return en


def error_codes(en):
    codes = {}
    pat = re.compile(r'HTTPException\(\s*\d+\s*,\s*"([a-z_]+)"')
    for f in SERVER.rglob("*.py"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in pat.finditer(line):
                codes.setdefault(m.group(1), []).append(f"{f.relative_to(SERVER).as_posix()}:{i}")
    missing = sorted(c for c in codes if f"error.{c}" not in en)
    print(f"== 2. server error codes: {len(codes)} raised, {len(missing)} without an `error.<code>` key")
    for c in missing:
        print(f"   {c}: {', '.join(codes[c][:4])}{' ...' if len(codes[c]) > 4 else ''}")


TEXT = re.compile(r">\s*([^<>{}\n]*[A-Za-z฀-๿][^<>{}\n]*?)\s*<")
ATTR = re.compile(r'\b(placeholder|title|aria-label|alt|label|description)="([^"{}]*[A-Za-z฀-๿][^"{}]*)"')
TOAST = re.compile(r'toast\.(?:success|error|info|warning|message)\(\s*["\'`]([^"\'`$]*[A-Za-z฀-๿][^"\'`$]*)["\'`]')
SKIP_VALUE = re.compile(r"^(?:[a-z][\w.-]*|[A-Z0-9_]+|https?://\S+|[\w/.-]+\.(?:png|svg|webp)|#\w+)$")  # ids, classes, urls


def hardcoded():
    print("== 3. hard-coded user-visible strings in .tsx (candidates)")
    total = 0
    for f in sorted(WEB.rglob("*.tsx")):
        rel = f.relative_to(WEB).as_posix()
        if rel == "i18n.tsx" or rel.startswith("components/ui/"):
            continue
        hits = []
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith(("//", "*", "/*", "import ")):
                continue
            for m in TEXT.finditer(line):
                v = m.group(1).strip()
                if len(v) >= 2 and not SKIP_VALUE.match(v) and not re.fullmatch(r"[\W\d_]+", v) and "=>" not in v and "&&" not in v:
                    hits.append((i, "text", v))
            prev = lines[i - 2].rstrip() if i >= 2 else ""
            if prev.endswith(">") and not prev.endswith("=>") and re.fullmatch(r"[^<>{}=;()\[\]]*[A-Za-z฀-๿][^<>{}=;()\[\]]*", s) and not s.startswith(("//", "*")):
                hits.append((i, "text-line", s))  # JSX text on a line of its own
            for m in ATTR.finditer(line):
                if not SKIP_VALUE.match(m.group(2)):
                    hits.append((i, m.group(1), m.group(2)))
            for m in TOAST.finditer(line):
                hits.append((i, "toast", m.group(1)))
        if hits:
            print(f"   {rel}")
            for i, kind, v in hits:
                print(f"     :{i} [{kind}] {v[:90]!r}")
            total += len(hits)
    print(f"   {total} candidates")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    en = parity()
    error_codes(en)
    hardcoded()
