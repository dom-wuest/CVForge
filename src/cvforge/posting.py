"""The text of an archived posting, for whoever reads it next - mostly Claude.

Postings are archived as printed PDFs (selectable text, the whole page), and
occasionally as a Markdown or text extract when a portal renders client-side.
Only reads; the file is never changed. pypdf is part of the `mcp` extra, so a
plain CLI install does not need it.
"""

from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = {".md", ".txt"}
POSTING_SUFFIXES = {".pdf", *TEXT_SUFFIXES}


def extract_text(path: Path) -> str:
    """The posting's text, or a one-line explanation of why there is none."""
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix != ".pdf":
        return f"[{path.name}: not a PDF or text file]"

    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(p for p in pages if p)
    if not text:
        # A screenshot saved as PDF has no text layer. Say so rather than
        # returning nothing, so the reader asks for a proper print.
        return f"[{path.name}: no text layer - print the posting to PDF instead of a screenshot]"
    return text


def archived(directory: Path) -> list[Path]:
    """The posting files in an application's posting/ folder."""
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in POSTING_SUFFIXES
    )
