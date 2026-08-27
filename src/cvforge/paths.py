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
SCHEMA = ROOT / "schema" / "cv.schema.json"
BUILD = ROOT / "build"
OUT = ROOT / "out"
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"

PRIVATE = DATA / "private.yaml"
PDF_MAIN = TEMPLATES / "pdf" / "main.typ"
WEB_TEMPLATES = TEMPLATES / "web"


def source(lang: str) -> Path:
    return DATA / f"cv-{lang}.yaml"


def resolved(lang: str) -> Path:
    return BUILD / f"cv-{lang}.json"


def pdf(lang: str) -> Path:
    return OUT / f"cv-{lang}.pdf"


def html(lang: str) -> Path:
    return OUT / f"cv-{lang}.html"
