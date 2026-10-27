"""Repo-relative paths, resolved once."""

from __future__ import annotations

from pathlib import Path


def find_root(start: Path | None = None) -> Path:
    """Locate the repo root by walking up for the marker files.

    Falls back to the package's own location, which is correct for the normal
    `uv run cvforge ...` case where the project is installed from this repo.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "schema").is_dir():
            return candidate
    return Path(__file__).resolve().parents[2]


ROOT = find_root()

DATA = ROOT / "data"
BUILD = ROOT / "build"
OUT = ROOT / "out"
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"

# One application per directory. Everything in it is gitignored except the
# _template scaffold - see .gitignore for why.
APPLICATIONS = ROOT / "applications"
APPLICATION_TEMPLATE = APPLICATIONS / "_template"

# Never committed: the signature scan and the pool of documents you attach to
# applications. Named only from data/private.yaml, which is itself gitignored,
# so no tracked file mentions these paths.
PRIVATE_ASSETS = ASSETS / "private"
PRIVATE_DOCUMENTS = PRIVATE_ASSETS / "documents"

PRIVATE = DATA / "private.yaml"

CV_SCHEMA = ROOT / "schema" / "cv.schema.json"
LETTER_SCHEMA = ROOT / "schema" / "letter.schema.json"
DOSSIER_SCHEMA = ROOT / "schema" / "dossier.schema.json"

CV_MAIN = TEMPLATES / "pdf" / "main.typ"
LETTER_MAIN = TEMPLATES / "letter" / "main.typ"


def display(path: Path) -> str:
    """Repo-relative where possible, absolute otherwise.

    `export` writes into the website's working copy, which is outside the repo,
    and Path.relative_to raises rather than reaching upward.
    """
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def source(lang: str) -> Path:
    return DATA / f"cv-{lang}.yaml"


def resolved(lang: str) -> Path:
    return BUILD / f"cv-{lang}.json"


def pdf(lang: str) -> Path:
    return OUT / f"cv-{lang}.pdf"


# ─── Cover letters ──────────────────────────────────────────────────────────
# A letter is keyed by application slug, not by language: it is written once,
# for one company, and the language is a property of that one application.


def application(slug: str) -> Path:
    return APPLICATIONS / slug


def letter_source(slug: str) -> Path:
    return application(slug) / "letter.yaml"


def dossier(slug: str) -> Path:
    return application(slug) / "dossier.yaml"


def attachments(slug: str) -> Path:
    """Where a one-off attachment for this application alone lives.

    Paths in a letter's `attachments:` are resolved against the application
    directory, so "attachments/portfolio.pdf" means this. Gitignored, like the
    dossier - a work sample is not repository content.
    """
    return application(slug) / "attachments"


def cv_override(slug: str) -> Path:
    """A CV tailored to this application alone, created by `cvforge new --cv`.

    A full copy of data/cv-<lang>.yaml rather than a patch: an application is
    a snapshot of what was sent, so later edits to the base CV must not change
    it retroactively - and the base CV feeds the website, so the tailoring must
    not happen there.
    """
    return application(slug) / "cv.yaml"


def cv_source(lang: str, slug: str | None = None) -> Path:
    """The CV an application uses: its own override if present, else the base.

    The one place that choice is made, so the letterhead, the attached CV and
    `check` cannot disagree about which file they read.
    """
    if slug is not None and cv_override(slug).is_file():
        return cv_override(slug)
    return source(lang)


def cv_resolved_for(slug: str) -> Path:
    """The resolved tailored CV. Never build/cv-<lang>.json, which the base CV's
    live preview reads and which must keep showing the base CV."""
    return BUILD / f"cv-app-{slug}.json"


def letter_resolved(slug: str) -> Path:
    return BUILD / f"letter-{slug}.json"


def letter_preview() -> Path:
    """Where `dev --letter` mirrors the resolved letter.

    Tinymist's --input flags are global to the workspace, so the preview cannot
    name a slug. It always reads this file, and the watcher keeps it current.
    """
    return BUILD / "letter-preview.json"


def letter_pdf(slug: str) -> Path:
    """The draft letter on its own, deliberately NOT inside the send folder.

    If drafts landed in the bundle, this sequence would send the wrong file:
    build the folder, tweak a sentence, rebuild just the letter to look at it,
    then drag the folder - which now holds a numbered stale letter next to an
    unnumbered fresh one.
    """
    return OUT / "letters" / f"{slug}.pdf"


def bundle(slug: str) -> Path:
    return OUT / "applications" / slug
