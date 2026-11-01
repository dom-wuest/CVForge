"""The memory a chat starts from: instructions, snippets, learnings.

A chat in Claude Desktop starts empty, and it has no Project library to fall
back on - the MCP server is all it can reach. So the server serves three
markdown files from <home>/guidance/, and they sync with the home:

    instructions.md   your standing rules - tone, content, process
    snippets.md       reusable paragraphs, DE and EN, collected from letters
    learnings.md      what Claude learned, one dated line per entry

The first two are yours: Claude reads them and never writes them. The third is
append-only for Claude (`remember`) and yours to condense or prune by hand -
there is no verb to edit or delete an entry, so a chat cannot quietly rewrite
what an earlier one learned.
"""

from __future__ import annotations

import datetime

from . import paths, resolve

FILES = ("instructions.md", "snippets.md", "learnings.md")

LEARNING_MAX = 500

LEARNINGS_HEADER = """\
# Learnings

What Claude learned while writing applications with you, one line per entry:
`- date · application · topic: lesson`. Claude only appends (the `remember`
tool); condense, merge or delete entries here by hand whenever you like.

"""


def read() -> dict[str, str | None]:
    """Each guidance file's text, or None when it does not exist."""
    out: dict[str, str | None] = {}
    for name in FILES:
        path = paths.GUIDANCE / name
        out[name] = path.read_text(encoding="utf-8") if path.is_file() else None
    return out


def entry_count() -> int:
    path = paths.GUIDANCE / "learnings.md"
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("- "))


def append_learning(text: str, slug: str | None = None, topic: str | None = None) -> str:
    """Append one entry to learnings.md and return the line written."""
    text = " ".join(text.split())
    topic = " ".join((topic or "").split())
    if not text:
        raise resolve.ResolveError("a learning needs text")
    if len(text) > LEARNING_MAX:
        raise resolve.ResolveError(
            f"a learning is one or two sentences - this one is {len(text)} characters, "
            f"the limit is {LEARNING_MAX}"
        )
    parts = [datetime.date.today().isoformat(), slug or "general"]
    line = "- " + " · ".join(parts) + (f" · {topic}" if topic else "") + f": {text}\n"

    path = paths.GUIDANCE / "learnings.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(LEARNINGS_HEADER, encoding="utf-8", newline="\n")
    elif not path.read_text(encoding="utf-8").endswith("\n"):
        line = "\n" + line  # hand-edited without a final newline
    # Appended, never rewritten: an entry you edited by hand a minute ago in
    # another window is not overwritten by a stale copy.
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line)
    return line.strip("\n")
