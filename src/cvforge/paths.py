"""Repo-relative paths, resolved once - and the home your own data lives in."""

from __future__ import annotations

import os
import re
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

# ─── Home ───────────────────────────────────────────────────────────────────
# Your own data - private.yaml, the signature, the certificates, every
# application - can live outside the repository, in a synced folder, so that a
# second machine has it and so that it is backed up at all. Gitignored files
# in a working copy have neither.
#
# Set once per machine with `cvforge home set <dir>`, which writes
# LOCAL_CONFIG (gitignored). $CVFORGE_HOME overrides it. With neither, the
# repository itself is the home and the layout is the one a fresh clone has:
# applications/, data/private.yaml, assets/private/.

HOME_ENV = "CVFORGE_HOME"
LOCAL_CONFIG = ROOT / "cvforge.local.toml"

# `home = '<dir>'`. A TOML literal string, so a Windows path needs no escaping.
_HOME_LINE = re.compile(r"""^\s*home\s*=\s*'([^']*)'\s*$""", re.MULTILINE)


def configured_home() -> tuple[Path | None, str | None]:
    """The home directory as configured, and where the setting came from.

    Read without validating it, so `cvforge home` can still report a setting
    that points at a folder which is not there.
    """
    raw = os.environ.get(HOME_ENV, "").strip()
    if raw:
        return Path(raw).expanduser(), f"${HOME_ENV}"
    if LOCAL_CONFIG.is_file():
        found = _HOME_LINE.search(LOCAL_CONFIG.read_text(encoding="utf-8"))
        if found and found.group(1).strip():
            return Path(found.group(1).strip()).expanduser(), LOCAL_CONFIG.name
    return None, None


def home_problem(home: Path | None, origin: str | None) -> str | None:
    """Why a configured home cannot be used, or None.

    A home that is set but missing - OneDrive not synced yet, a laptop with a
    different user folder - is an error rather than a quiet fallback to the
    repository. Falling back would scaffold the next application inside the
    working copy, where the other machine never sees it.
    """
    if home is None:
        return None
    if not home.is_absolute():
        return f"{origin} sets the home to {home}, which is not an absolute path"
    if not home.is_dir():
        return (
            f"{origin} sets the home to {home}, which does not exist. Wait for the sync, "
            f"or point it elsewhere with `cvforge home set <dir>`."
        )
    return None


HOME, HOME_SOURCE = configured_home()
HOME_PROBLEM = home_problem(HOME, HOME_SOURCE)

# Where private.yaml's relative paths (`signature`, `documents[].file`) start.
PRIVATE_BASE = HOME or ROOT

# One application per directory. In the repository, everything in it is
# gitignored except the _template scaffold - see .gitignore for why. The
# scaffold always stays in the repository: it is code, not your data.
APPLICATIONS = (HOME or ROOT) / "applications"
APPLICATION_TEMPLATE = ROOT / "applications" / "_template"

# Never committed: the signature scan and the pool of documents you attach to
# applications. Named only from private.yaml, which is itself never committed,
# so no tracked file mentions these paths.
PRIVATE_ASSETS = HOME / "private" if HOME else ASSETS / "private"
PRIVATE_DOCUMENTS = PRIVATE_ASSETS / "documents"

PRIVATE = HOME / "private.yaml" if HOME else DATA / "private.yaml"

# Standing instructions, reusable text and what was learned along the way -
# the memory a chat in Claude Desktop starts from. Yours, like the
# applications it was learned from, so it moves with the home (gitignored when
# the repository is the home). See guidance.py.
GUIDANCE = (HOME or ROOT) / "guidance"

# Every application on one local page, rebuilt from the dossiers. Beside
# applications/ so its links are relative to the home and work on every machine
# that syncs it; it holds recruiters' details, so never anywhere it could be
# published (gitignored when the repository is the home). See dashboard.py.
DASHBOARD = (HOME or ROOT) / "dashboard.html"
DASHBOARD_TEMPLATE = ROOT / "templates" / "dashboard" / "dashboard.html"

SCHEMA = ROOT / "schema"
CV_SCHEMA = SCHEMA / "cv.schema.json"
LETTER_SCHEMA = SCHEMA / "letter.schema.json"
DOSSIER_SCHEMA = SCHEMA / "dossier.schema.json"

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


def private_path(rel: str) -> Path:
    """A path named in private.yaml, which is relative to the home."""
    return PRIVATE_BASE / rel


def schema_mirror() -> Path | None:
    """A copy of schema/ inside the home, or None when the repo is the home.

    Every application file carries `$schema=../../schema/...`. That resolves to
    the repository's schema/ when applications/ is in the repository, and to
    this mirror when it is in the home - the same relative hint, on every
    machine, whatever the repository's path there.
    """
    return HOME / "schema" if HOME else None


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


def draft_cv_pdf(slug: str) -> Path:
    """The CV a draft build produces, beside the draft letter and for the same
    reason: out/, not send/, so looking at a draft can never touch what was sent."""
    return OUT / "drafts" / f"{slug}-cv.pdf"


def inbox() -> Path:
    """Where a posting PDF waits before it has an application.

    The hand-over to the MCP server: a file attached to a chat never reaches a
    local process, so the posting is printed to PDF into this folder instead.
    """
    return (HOME or ROOT) / "inbox"


def bundle(slug: str) -> Path:
    """The send-ready folder, next to the sources it was built from.

    Inside the application rather than under out/, so the home holds what was
    sent as well as what it was made from. `apply` empties it before every
    build, which is why it is a folder of its own: nothing else lives in it.
    """
    return application(slug) / "send"
