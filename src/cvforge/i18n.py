"""The one place language-dependent strings live.

Neither renderer carries its own copy: `resolve` emits the resolved dict for the
target language into build/cv-<lang>.json under `labels`, and the templates read
it from there. Adding a language means adding a key here and a data/cv-<lang>.yaml.

Month abbreviations live in dates.py, next to the code that uses them.
"""

from __future__ import annotations

LABELS: dict[str, dict[str, str]] = {
    "en": {
        # Section headings
        "profile": "Profile",
        "experience": "Experience",
        "education": "Education",
        "projects": "Projects",
        "skills": "Skills",
        "languages": "Languages",
        "interests": "Interests",
        # Timeline
        "present": "Present",
        # Education meta line
        "thesis": "Thesis",
        "minor": "Minor",
        "specialization": "Specialization",
        "grade": "Grade",
        "grade_current": "Current Grade",
        # Misc
        "page": "Page",
    },
    "de": {
        "profile": "Profil",
        "experience": "Berufserfahrung",
        "education": "Ausbildung",
        "projects": "Projekte",
        "skills": "Kenntnisse",
        "languages": "Sprachen",
        "interests": "Interessen",
        "present": "heute",
        "thesis": "Abschlussarbeit",
        "minor": "Nebenfach",
        "specialization": "Profilfach",
        "grade": "Note",
        "grade_current": "Aktuelle Note",
        "page": "Seite",
    },
}

LANGS = tuple(LABELS)

# Separator between the fields of a composed meta line. One character, one
# place, so "Thesis: X - Minor: Y - Grade 2.1" never grows a dangling one.
META_SEP = " – "  # en dash


def labels(lang: str) -> dict[str, str]:
    try:
        return dict(LABELS[lang])
    except KeyError:
        raise KeyError(f"unknown language {lang!r}, expected one of {', '.join(LANGS)}") from None
