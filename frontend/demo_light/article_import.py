"""Bring a report written somewhere else into the library.

Two of the four engines are not this app's. Deep Research and the agents
researcher write their reports inside their own applications, and until now
that is where a report stopped: the library held only what STORM and
Co-STORM wrote themselves, so half of what a member produced lived outside
the one place they would go looking for it.

An import is the way across, and deliberately the dull one. It asks the
sibling for nothing — no shared session, no knowledge of who is signed in,
and no reading of another application's private browser storage, which would
work today and break silently the next time that application is updated, in
a way nobody would notice until a report failed to arrive.

The citation numbers line up for free. Deep Research's own report prompt says
to "use numbered citations like [1] that match learning index values", which
is the convention STORM already writes and the library already renders. So
when an imported report carries a list of its sources, this rebuilds the
citation file from that list, and the reference panel works on an imported
report exactly as it does on a written one.
"""

import json
import re
import time
from pathlib import Path

import article_store
from knowledge_storm.utils import truncate_filename

# The names the library looks for. `storm_gen_article_polished.txt` is what
# `article_store.completed_article` reads first, so an imported report counts
# as a finished one everywhere else without any page being taught about it.
ARTICLE_FILE = "storm_gen_article_polished.txt"
CITATIONS_FILE = "url_to_info.json"
ORIGIN_FILE = "import_info.json"

# Where a list of sources starts. English and Thai, with or without a number
# in front, because a report that numbers its sections writes "## 5. Sources".
_SOURCE_HEADING = re.compile(
    r"^(?P<hashes>#{1,4})\s*(?:\d+[.)]\s*)?"
    r"(?:sources?|references?|citations?|bibliography|works\s+cited"
    r"|แหล่งอ้างอิง|เอกสารอ้างอิง|รายการอ้างอิง|อ้างอิง|แหล่งที่มา)"
    r"\s*:?\s*$",
    re.IGNORECASE,
)

# A source's own number, when it has one: [3], 3. or 3). Respected rather
# than counted over, because that number is what the body of the article
# points at, and renumbering would break every citation at once.
_LEADING_NUMBER = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)\s*[.):])\s*")

_BULLET = re.compile(r"^\s*[*+•-]\s+")
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^\s)]+)\)")
_BARE_URL = re.compile(r"https?://[^\s)<>\"']+")
_TITLE_LINE = re.compile(r"^#\s+(.+?)\s*$")
_ANY_HEADING = re.compile(r"^(#{1,6})\s")

# A filesystem counts a name's bytes, not its characters, and the usual limit
# for one path component is 255. `truncate_filename` caps at 125 characters,
# which is right for English and wrong for Thai: every Thai character is
# three bytes in UTF-8, so the first real report imported here — a 99
# character Thai heading — came to 293 bytes, and the directory could not be
# created at all. What the page showed for that was "the report could not be
# moved", which is unhelpful and also not what happened.
#
# 200 rather than 255, so a name is still a name after the filesystem, the
# encoding and any suffix have all had their say.
NAME_BYTES = 200


def _fit(name, budget=NAME_BYTES):
    """`name` cut to `budget` bytes of UTF-8, never through a character."""
    encoded = name.encode("utf-8")
    if len(encoded) <= budget:
        return name
    return encoded[:budget].decode("utf-8", "ignore").rstrip("_")


def _sources_block(text):
    """The lines under a sources heading, or None if the report has none.

    The last such heading wins: a report may say "sources" in passing on its
    way to the list that actually ends it. The block stops at the next
    heading of the same level or higher, because a list of sources is usually
    the end of a report but is not always the end of the file.
    """
    lines = text.splitlines()
    start = None
    depth = 0
    for number, line in enumerate(lines):
        match = _SOURCE_HEADING.match(line.strip())
        if match:
            start = number + 1
            depth = len(match.group("hashes"))
    if start is None:
        return None

    block = []
    for line in lines[start:]:
        heading = _ANY_HEADING.match(line.strip())
        if heading and len(heading.group(1)) <= depth:
            break
        block.append(line)
    return block


def parse_sources(text):
    """[(number, title, url)] for the sources a report lists, in citation order.

    An empty list is not a failure. A report without a list still imports; it
    simply arrives without a reference panel, which is the truth about it.
    """
    block = _sources_block(text)
    if block is None:
        return []

    found = []
    seen = set()
    for line in block:
        stripped = _BULLET.sub("", line.strip())
        if not stripped:
            continue

        numbered = _LEADING_NUMBER.match(stripped)
        number = None
        if numbered:
            number = int(numbered.group(1) or numbered.group(2))
            stripped = stripped[numbered.end():]

        link = _MARKDOWN_LINK.search(stripped)
        if link:
            title, url = link.group(1).strip(), link.group(2)
        else:
            bare = _BARE_URL.search(stripped)
            if not bare:
                continue
            url = bare.group(0)
            # What comes before the address is the source's name, less the
            # punctuation that was holding the two together.
            title = stripped[: bare.start()].strip().strip("-–—:|,• ")

        url = url.rstrip(".,;)")
        if not url or url in seen:
            continue
        seen.add(url)
        found.append((number, title or url, url))

    # A report that numbered its own sources keeps those numbers. One that
    # did not is numbered by the order it listed them in, which is the order
    # its body cites them in.
    return [
        (number if number is not None else position, title, url)
        for position, (number, title, url) in enumerate(found, start=1)
    ]


def citations(sources):
    """`url_to_info.json` in the shape the library already reads, or None.

    Two halves, as STORM writes it: a url -> citation number map, and a
    url -> record map that the reference panel renders from.
    """
    if not sources:
        return None
    return {
        "url_to_unified_index": {url: number for number, _, url in sources},
        "url_to_info": {
            url: {
                "url": url,
                "title": title,
                "description": "",
                # The panel shows quoted passages under a source. An imported
                # report has none — the reading happened in the application
                # that did the research, and the passages stayed there — and
                # an empty list is honest where a repeated title is filler.
                "snippets": [],
                "meta": {"query": ""},
                "citation_uuid": -1,
            }
            for number, title, url in sources
        },
    }


def suggested_title(text, filename=""):
    """The report's own first heading, falling back to the file's name."""
    for line in text.splitlines():
        heading = _TITLE_LINE.match(line.strip())
        if heading:
            return heading.group(1).strip()
    return Path(filename or "").stem.replace("_", " ").strip()


def directory_name(title):
    """The library keys an article by its directory, with spaces as `_`.

    Raises ValueError for a title that cannot be one, which is the same check
    the article writer makes before it starts a run.
    """
    cleaned = (title or "").strip().replace(" ", "_")
    cleaned = cleaned.replace("/", "_").replace("\\", "_")
    # Both limits: 125 characters as the rest of the app counts them, and
    # 200 bytes as the filesystem does. See NAME_BYTES.
    cleaned = _fit(truncate_filename(cleaned))
    article_store.validate_name(cleaned)
    return cleaned


def save(root, title, text, origin=""):
    """Write the report into `root` as an article; returns its directory name.

    Never overwrites. An import that quietly replaced a report of the same
    name would be a way to lose work that nothing else in the library offers,
    and the report already there is the one with a run behind it.
    """
    if not (text or "").strip():
        raise ValueError("The report is empty")

    name = directory_name(title)
    folder = Path(root) / name
    if folder.exists() or folder.is_symlink():
        raise FileExistsError(name)

    folder.mkdir(parents=True)
    (folder / ARTICLE_FILE).write_text(text, encoding="utf-8")

    sources = parse_sources(text)
    built = citations(sources)
    if built:
        (folder / CITATIONS_FILE).write_text(
            json.dumps(built, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Where this came from, so a report that arrived rather than ran can say
    # so later. Nothing reads it yet; it costs one small file to be able to.
    (folder / ORIGIN_FILE).write_text(
        json.dumps(
            {
                "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "origin": origin,
                "sources": len(sources),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return name
