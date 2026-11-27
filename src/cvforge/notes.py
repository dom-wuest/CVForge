"""The Markdown that dossier prose may use, parsed for the dashboard.

Notes are written by hand and by Claude Desktop, which summarises calls and
emails in Markdown. The dashboard shows a fixed subset of it:

    **bold**  __bold__  *italic*  _italic_  `code`
    https://… and name@host as links, [text](url) - http, https and mailto only
    "- " / "* " / "+ " lists, "1. " numbered lists, "> " quotes

Anything else - headings, tables, images, HTML - stays literal text, and so
does any marker that does not pair up: a stray ** shows as **. That is the
right failure for notes, which are read, not published.

Why not a Markdown library: they produce HTML, and the dashboard never builds
markup from data - the dossiers carry other people's words, a pasted email
among them. So this module emits structure, not markup: blocks of inline
*runs*, each a piece of text with the marks that apply to it,

    {"t": "on-site", "b": True}    {"t": "the posting", "href": "https://…"}

and the page builds <strong>, <a> and friends around text nodes. Links are
limited to http, https and mailto here, and again on the page.

Emphasis follows CommonMark's flanking rule closely enough for notes: an
opening marker is followed by a non-space and a closing one preceded by one,
and none touches a letter or digit on the outside. So `*.pdf and *.png`, 5*3*2
and posting_v2_final.pdf stay as they are.
"""

from __future__ import annotations

import re
from typing import Any

Run = dict[str, Any]

# For the MCP server's instructions and docstrings, so Claude writes what the
# dashboard can show. Keep it in step with the module docstring.
SUBSET = (
    "Markdown: **bold**, *italic*, `code`, links (bare URLs and e-mail "
    'addresses, or [text](url) with http, https or mailto), "- " lists, '
    '"1. " numbered lists and "> " for quoting an email word for word. No '
    "headings, tables, images or HTML - the dashboard shows those as plain text."
)

SCHEMES = ("http://", "https://", "mailto:")

# Order is priority when two match at the same position: a code span protects
# its content, a link its label, and a URL beats the emphasis inside it.
_INLINE = (
    ("code", re.compile(r"`([^`\n]+)`")),
    ("link", re.compile(r"\[([^\]\n]+)\]\(\s*([^\s()]+)\s*\)")),
    ("url", re.compile(r"https?://[^\s<>`*\[\]]+")),
    ("email", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("both", re.compile(r"(?<![\w*])\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*(?![\w*])")),
    (
        "bold",
        re.compile(r"(?<!\w)\*\*(?=\S)(.+?)(?<=\S)\*\*(?!\w)|(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)"),
    ),
    (
        "italic",
        re.compile(
            r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])"
            r"|(?<![\w_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w_])"
        ),
    ),
)

# A sentence ends after a URL more often than the URL does.
_URL_TAIL = ".,;:!?'\""

_BULLET = re.compile(r"[-*+] +(.*)")
_NUMBER = re.compile(r"(\d{1,3})[.)] +(.*)")
_QUOTE = re.compile(r">[ \t]?(.*)")


def _add(runs: list[Run], text: str, marks: dict[str, Any]) -> None:
    if not text:
        return
    if runs and {k: v for k, v in runs[-1].items() if k != "t"} == marks:
        runs[-1]["t"] += text
    else:
        runs.append({"t": text, **marks})


def _trim_url(url: str) -> str:
    while url and (url[-1] in _URL_TAIL or (url[-1] == ")" and url.count(")") > url.count("("))):
        url = url[:-1]
    return url


def inline(text: str, marks: dict[str, Any] | None = None) -> list[Run]:
    """`text` as runs. Unpaired markers and unknown syntax stay literal."""
    marks = marks or {}
    runs: list[Run] = []
    pos = 0
    while pos < len(text):
        best: tuple[str, re.Match[str]] | None = None
        for kind, pattern in _INLINE:
            found = pattern.search(text, pos)
            if found and (best is None or found.start() < best[1].start()):
                best = (kind, found)
        if best is None:
            break
        kind, m = best
        _add(runs, text[pos : m.start()], marks)
        end = m.end()
        if kind == "code":
            _add(runs, m[1], {**marks, "code": True})
        elif kind == "link":
            label, href = m[1], m[2]
            if href.lower().startswith(SCHEMES) and "href" not in marks:
                runs += inline(label, {**marks, "href": href})
            else:  # another scheme, or a link inside a link: show it as written
                _add(runs, m[0], marks)
        elif kind in ("url", "email"):
            found = _trim_url(m[0]) if kind == "url" else m[0]
            end = m.start() + len(found)
            if "href" in marks:
                _add(runs, found, marks)
            else:
                href = found if kind == "url" else "mailto:" + found
                _add(runs, found, {**marks, "href": href})
        elif kind == "both":
            runs += inline(m[1], {**marks, "b": True, "i": True})
        else:
            flag = "b" if kind == "bold" else "i"
            runs += inline(m[1] or m[2], {**marks, flag: True})
        pos = end
    _add(runs, text[pos:], marks)
    return _merge(runs)


def _merge(runs: list[Run]) -> list[Run]:
    out: list[Run] = []
    for run in runs:
        _add(out, run["t"], {k: v for k, v in run.items() if k != "t"})
    return out


def plain(text: str) -> str:
    """One line with the markers removed - for titles, where emphasis is noise."""
    return "".join(run["t"] for run in inline(" ".join(str(text or "").split())))


def paragraph(text: str) -> list[Run]:
    """A one-paragraph field (summary, about): whitespace collapsed, then runs."""
    return inline(" ".join(str(text or "").split()))


def blocks(text: str) -> list[dict[str, Any]]:
    """Notes as blocks: {"p": runs}, {"ul": [runs]}, {"ol": [runs], "start": n}
    or {"quote": [runs per line]}.

    A blank line ends a paragraph, list or quote. In a list, an indented line
    continues the item above it. A quote keeps its line breaks, because what
    it quotes - an email - has them; a paragraph joins its lines.
    """
    out: list[dict[str, Any]] = []
    para: list[str] = []
    current: dict[str, Any] | None = None  # the list or quote being filled

    def flush() -> None:
        if para:
            out.append({"p": " ".join(para)})
            para.clear()

    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            flush()
            current = None
            continue
        quote = _QUOTE.match(line)
        item = _BULLET.match(line) or _NUMBER.match(line)
        if quote:
            flush()
            if current is None or "quote" not in current:
                current = {"quote": []}
                out.append(current)
            current["quote"].append(quote[1].strip())
        elif item:
            flush()
            kind = "ul" if item.re is _BULLET else "ol"
            if current is None or kind not in current:
                current = {kind: []}
                if kind == "ol":
                    current["start"] = int(item[1])
                out.append(current)
            current[kind].append(item[item.lastindex].strip())
        elif current is not None and "quote" not in current and raw[:1] in (" ", "\t"):
            items = current.get("ul") or current["ol"]
            items[-1] += " " + line
        else:
            current = None
            para.append(line)
    flush()

    for block in out:
        if "p" in block:
            block["p"] = inline(block["p"])
        for key in ("ul", "ol", "quote"):
            if key in block:
                block[key] = [inline(line) for line in block[key]]
    return out


_UNSUPPORTED = (
    ("headings", re.compile(r"(?m)^ {0,3}#{1,6} \S")),
    ("tables", re.compile(r"(?m)^\s*\|.*\|\s*$")),
    ("images", re.compile(r"!\[[^\]]*\]\(")),
)


def unsupported(text: str) -> list[str]:
    """The kinds of Markdown in `text` the dashboard will show as plain text."""
    return [name for name, pattern in _UNSUPPORTED if pattern.search(str(text or ""))]
