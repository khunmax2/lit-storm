"""Local report storage, always rooted in the signed-in user's workspace.

Deleting moves a whole report into that workspace's trash. The run ledger is
left intact: removing a report does not refund research quota.
"""

from pathlib import Path
from uuid import uuid4


def validate_name(name):
    """Accept one visible directory name, never a path or reserved directory."""
    if (
        not isinstance(name, str)
        or not name
        or name.startswith(".")
        or "/" in name
        or "\\" in name
        or "\0" in name
    ):
        raise ValueError("Invalid report directory name")
    return name


def workspace(root, owner):
    """No anonymous fallback to the old, shared report directory."""
    if not owner:
        raise PermissionError("A signed-in user is required")
    path = Path(root) / validate_name(owner)
    if path.is_symlink():
        raise ValueError("Workspace cannot be a symbolic link")
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def _report(root, name):
    path = Path(root) / validate_name(name)
    if path.is_symlink():
        raise ValueError("Report directory cannot be a symbolic link")
    return path


def list_articles(root):
    articles = {}
    for path in Path(root).iterdir():
        if path.name.startswith(".") or path.is_symlink() or not path.is_dir():
            continue
        articles[path.name] = {
            file.name: str(file.resolve())
            for file in path.iterdir()
            if file.is_file() and not file.is_symlink()
        }
    return articles


def completed_article(files):
    """An empty polished file must not hide a usable draft."""
    for name in ("storm_gen_article_polished.txt", "storm_gen_article.txt"):
        filename = files.get(name)
        if not filename:
            continue
        path = Path(filename)
        try:
            if not path.is_symlink() and path.is_file() and path.read_text(encoding="utf-8").strip():
                return str(path)
        except (OSError, UnicodeError):
            continue
    return None


def _trash(root):
    path = Path(root) / ".trash"
    if path.is_symlink():
        raise ValueError("Trash cannot be a symbolic link")
    return path


def trash_article(root, name):
    source = _report(root, name)
    if not source.is_dir():
        raise FileNotFoundError(name)
    entry = _trash(root) / uuid4().hex
    entry.mkdir(parents=True)
    try:
        source.rename(entry / name)
    except OSError:
        entry.rmdir()
        raise
    return entry.name


def list_trash(root):
    trash = _trash(root)
    if not trash.exists():
        return {}
    entries = {}
    for entry in sorted(trash.iterdir(), key=lambda path: path.name):
        if entry.is_symlink() or not entry.is_dir():
            continue
        reports = list_articles(entry)
        if len(reports) == 1:
            entries[entry.name] = next(iter(reports))
    return entries


def restore_article(root, entry_id):
    # Re-read the user's own trash; a caller cannot supply an arbitrary path.
    validate_name(entry_id)
    name = list_trash(root).get(entry_id)
    if name is None:
        raise FileNotFoundError(entry_id)
    destination = _report(root, name)
    if destination.exists():
        raise FileExistsError(name)
    entry = _trash(root) / entry_id
    (entry / name).rename(destination)
    entry.rmdir()
    return name
