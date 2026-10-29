"""The one place language-dependent strings live.

Neither renderer carries its own copy: `resolve` emits the resolved dict for the
target language into build/cv-<lang>.json under `labels`, and the templates read
it from there. Adding a language means adding a key here and a data/cv-<lang>.yaml.

Month abbreviations live in dates.py, next to the code that uses them.

Two tables, because the two documents have separate audiences: LABELS ships to
the website inside every resolved CV, LETTER_LABELS never leaves your machine.
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
        "grade_preliminary": "Preliminary Grade",
        "coursework": "Relevant coursework",
        # Misc
        "page": "Page",
    },
    "de": {
        "profile": "Profil",
        "experience": "Berufserfahrung",
        "education": "Bildungsweg",
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
        "grade_preliminary": "Vorläufige Note",
        "coursework": "Relevante Vorlesungen",
        "page": "Seite",
    },
}

# Cover letter strings, deliberately a SEPARATE table rather than more keys in
# LABELS. `resolve.derive` emits the whole LABELS table into every
# build/cv-<lang>.json, and that artifact is copied verbatim onto the website -
# so a letter's salutation would ship to every visitor for nothing.
LETTER_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "subject_prefix": "Application for",
        "subject_reference": "Reference",
        "salutation_default": "Dear Hiring Team,",
        "closing": "Kind regards",
        "enclosures": "Enclosures",
        # Used to name the files in an application's send/ folder.
        "file_letter": "Cover_Letter",
        "file_cv": "CV",
    },
    "de": {
        "subject_prefix": "Bewerbung als",
        "subject_reference": "Kennziffer",
        "salutation_default": "Sehr geehrte Damen und Herren,",
        "closing": "Mit freundlichen Grüßen",
        "enclosures": "Anlagen",
        "file_letter": "Anschreiben",
        "file_cv": "Lebenslauf",
    },
}

LANGS = tuple(LABELS)

# Separator between the fields of a composed meta line. One character, one
# place, so "Thesis: X - Minor: Y - Grade 2.1" never grows a dangling one.
META_SEP = " – "  # en dash


def _lookup(table: dict[str, dict[str, str]], lang: str) -> dict[str, str]:
    try:
        return dict(table[lang])  # a copy, so callers may mutate
    except KeyError:
        raise KeyError(f"unknown language {lang!r}, expected one of {', '.join(LANGS)}") from None


def labels(lang: str) -> dict[str, str]:
    return _lookup(LABELS, lang)


def letter_labels(lang: str) -> dict[str, str]:
    return _lookup(LETTER_LABELS, lang)
