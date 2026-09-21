"""Check the seams lit-storm depends on in agents-deep-research.

Reports, never forces — the same rule the other sibling's checker follows.
A merge from upstream that breaks one of these does not break the build; it
prints here, and somebody decides. Forcing would mean this file blocking an
upstream fix, which is the wrong way round.

Four things are checked, and each one is here because losing it broke
something real:

1. `openrouter.ai` in `structured_output_providers`. Without it every
   OpenRouter model takes the text fallback and every run dies on the first
   agent, with the JSON schema parsed as the answer.
2. `_log_message` on both researchers. `web/server.py` subclasses and
   overrides it to feed the progress panel — that is the only reason the
   page is not a five-minute blank.
3. `embed`, `lang` and `theme` read by the page. The host app frames it
   with all three, and without them the frame shows a second application's
   language and theme controls under its own.
4. `/healthz`. The host app asks before it frames, so a stopped container
   says so instead of loading a browser error page inside the layout.

    python check_agents_research_contract.py [path-to-repo]
"""

import ast
import pathlib
import sys

DEFAULT = pathlib.Path(__file__).resolve().parents[3] / "agents-deep-research"


def _read(root, relative):
    path = root / relative
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _providers(source):
    """The values actually assigned to `structured_output_providers`.

    Read from the syntax tree rather than searched for in the text. The first
    version of this asked whether "openrouter.ai" appeared anywhere in the
    file and passed while the list was broken, because the comment explaining
    why the entry matters names it three times. A checker that cannot fail is
    worse than no checker: it is a green tick with nothing behind it.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "structured_output_providers" not in names:
            continue
        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
            found += [
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
    return found


def check(root):
    """Yields (ok, headline, detail) for each seam."""
    config = _read(root, "deep_researcher/llm_config.py")
    if config is None:
        yield False, "llm_config.py missing", "the library's layout has changed"
    else:
        yield (
            "openrouter.ai" in _providers(config),
            "OpenRouter counted as structured-output capable",
            "add it back to structured_output_providers in "
            "model_supports_structured_output, or every run dies on the "
            "first agent",
        )

    for name in ("iterative_research.py", "deep_research.py"):
        source = _read(root, f"deep_researcher/{name}")
        if source is None:
            yield False, f"{name} missing", "the library's layout has changed"
            continue
        has_hook = any(
            isinstance(node, ast.FunctionDef) and node.name == "_log_message"
            for node in ast.walk(ast.parse(source))
        )
        yield (
            has_hook,
            f"_log_message still on {name}",
            "web/server.py overrides it for the progress panel; if it is "
            "gone, find what replaced it",
        )

    page = _read(root, "web/static/index.html")
    if page is None:
        yield False, "web/static/index.html missing", "our web surface is gone"
    else:
        for parameter in ("embed", "lang", "theme"):
            yield (
                f'"{parameter}"' in page or f"'{parameter}'" in page,
                f"page reads ?{parameter}",
                "the host app frames it with all three",
            )

    server = _read(root, "web/server.py")
    if server is None:
        yield False, "web/server.py missing", "our web surface is gone"
    else:
        yield (
            "/healthz" in server,
            "/healthz served",
            "the host app asks before it frames; without it a stopped "
            "container shows a browser error inside the tab",
        )


def main():
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not root.exists():
        print(f"not found: {root}")
        print("pass the path to the agents-deep-research checkout.")
        return 2

    print(f"checking {root}\n")
    broken = 0
    for ok, headline, detail in check(root):
        print(f"  {'ok  ' if ok else 'GONE'}  {headline}")
        if not ok:
            broken += 1
            print(f"        {detail}")

    print()
    if broken:
        print(f"{broken} seam(s) gone. Nothing is blocked — decide what to do.")
    else:
        print("every seam intact.")
    # Zero either way: this reports, it does not gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
