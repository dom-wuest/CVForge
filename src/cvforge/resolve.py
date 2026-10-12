"""Load -> validate -> merge private -> derive -> write build/cv-<lang>.json.

This is the only module that reads YAML and the only one that knows
data/private.yaml exists. Both renderers consume the resolved JSON and nothing
else, which is what keeps a third target (plain-text, JSON-LD, an ATS variant)
addable without touching the data.

Everything a renderer would otherwise have to compute is derived here:
formatted date ranges, the education meta line, the section labels. Renderers
stay dumb on purpose - the Typst one cannot easily do string logic, and
duplicating it in the HTML one is how the two drift apart.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from . import dates, i18n, paths

PROFILES = ("full", "public")


class ResolveError(Exception):
    """A user-fixable problem in the data. Printed without a traceback."""


# ─────────────────────────────────────────────────────────────────────────────
# Load and validate
# ─────────────────────────────────────────────────────────────────────────────


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ResolveError(f"no such file: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ResolveError(f"{path} does not contain a YAML mapping")
    return data


def _branch_errors(err: Any, limit: int = 3) -> list[str]:
    """Distinct complaints from the branches of a failed oneOf/anyOf."""
    seen: list[str] = []
    # Deepest path first: a complaint about a specific field is more useful
    # than one about the whole value.
    for sub in sorted(err.context or [], key=lambda e: -len(list(e.absolute_path))):
        message = sub.message if not list(sub.absolute_path) else f"{sub.json_path}: {sub.message}"
        if message not in seen:
            seen.append(message)
    return seen[:limit]


def validate_against(data: dict[str, Any], schema_path: Path, label: str) -> None:
    """Validate against a JSON Schema, reporting the offending node.

    The schema's `type: string` on dates is what catches an unquoted `2021-10`,
    which yaml.safe_load silently turns into a datetime.date.

    `label` names the source file in the error, so the reader knows which of
    several YAML files is being complained about.
    """
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        lines = [f"{label} failed validation:"]
        for err in errors[:10]:
            lines.append(f"  at {err.json_path}: {err.message}")
            # A `oneOf` (a skills item is a name *or* a {name, rating} mapping)
            # only reports "is not valid under any of the given schemas", which
            # says nothing about what is actually wrong. There is no reliable
            # way to guess which branch was intended, so show what each one
            # objected to and let the reader recognise their own mistake.
            for sub in _branch_errors(err):
                lines.append(f"      - {sub}")
        if len(errors) > 10:
            lines.append(f"  ... and {len(errors) - 10} more")
        raise ResolveError("\n".join(lines))


def validate(data: dict[str, Any], lang: str) -> None:
    """Validate one CV file, then check it declares the language it is named for."""
    validate_against(data, paths.CV_SCHEMA, paths.source(lang).name)

    declared = data["meta"]["lang"]
    if declared != lang:
        raise ResolveError(
            f"at $.meta.lang: declared {declared!r} but the file is data/cv-{lang}.yaml"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Private data
# ─────────────────────────────────────────────────────────────────────────────


def merge_private(data: dict[str, Any], profile: str, *, quiet: bool = False) -> list[str]:
    """Apply data/private.yaml to the contacts, per the resolve rules.

    `--profile public` ignores the file entirely, even when it exists - that is
    the guarantee the HTML target depends on. `--profile full` merges it when
    present and never fails when it is not: a fresh clone and CI must both
    produce a valid PDF from the committed placeholders alone.

    Returns informational messages for the caller to print.
    """
    notes: list[str] = []
    contacts = data.get("contacts", [])

    if profile == "public":
        # Drop the contacts that must never leave this machine, and reset any
        # that private.yaml would have refined back to their committed value.
        kept = [c for c in contacts if c.get("private") != "hidden"]
        dropped = len(contacts) - len(kept)
        data["contacts"] = kept
        if dropped and not quiet:
            notes.append(f"profile=public: omitted {dropped} private contact(s)")
        return notes

    if not paths.PRIVATE.is_file():
        placeholders = [c["id"] for c in contacts if c.get("private")]
        if placeholders and not quiet:
            notes.append(
                f"no {paths.PRIVATE.relative_to(paths.ROOT).as_posix()}; using placeholders for: "
                + ", ".join(placeholders)
                + "  (copy data/private.example.yaml to start)"
            )
        return notes

    private = load_yaml(paths.PRIVATE)
    overrides = private.get("contacts") or {}
    if not isinstance(overrides, dict):
        raise ResolveError(f"{paths.PRIVATE}: `contacts` must be a mapping keyed by contact id")

    by_id = {c["id"]: c for c in contacts}
    unknown = sorted(set(overrides) - set(by_id))
    if unknown and not quiet:
        notes.append(f"{paths.PRIVATE.name}: ignoring unknown contact id(s): {', '.join(unknown)}")

    applied = []
    for cid, override in overrides.items():
        target = by_id.get(cid)
        if target is None:
            continue
        if not isinstance(override, dict):
            raise ResolveError(f"{paths.PRIVATE}: contacts.{cid} must be a mapping")
        for key in ("value", "url"):
            if key in override and override[key] is not None:
                target[key] = override[key]
        applied.append(cid)
    if applied and not quiet:
        notes.append("merged private values for: " + ", ".join(applied))
    return notes


# ─────────────────────────────────────────────────────────────────────────────
# Derivation
# ─────────────────────────────────────────────────────────────────────────────


def clean(value: Any) -> Any:
    """Normalise the whitespace YAML block scalars leave behind.

    Two artifacts, both invisible in the source:

    - `>` folds internal newlines into spaces, so the trailing one is spurious.
    - A line ending in a space folds to *two* spaces, because the fold adds one
      of its own. Trailing whitespace is invisible in an editor but shows up in
      the rendered PDF as a visible gap mid-sentence.

    Runs of spaces and tabs collapse; newlines never do, so the deliberate line
    breaks of a `|` literal block survive.
    """
    if isinstance(value, str):
        return re.sub(r"[ \t]{2,}", " ", value.rstrip())
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    return value


def _skill_item(item: Any) -> dict[str, Any]:
    """Normalise a skills entry to {name, rating}.

    The YAML accepts either a bare string or a mapping with a rating, because
    most items want neither the noise nor the claim. The renderers should not
    have to care, so they always get the mapping.
    """
    if isinstance(item, str):
        return {"name": item, "rating": None, "note": None}
    return {"name": item["name"], "rating": item.get("rating"), "note": item.get("note")}


def _author(item: Any) -> dict[str, Any]:
    """Normalise a project author to {name, me, break_after}, like skill items."""
    if isinstance(item, str):
        return {"name": item, "me": False, "break_after": False}
    return {
        "name": item["name"],
        "me": item.get("me", False),
        "break_after": item.get("break_after", False),
    }


def _one_line(value: str | None) -> str | None:
    """Collapse to a single line, for fields composed into a meta line."""
    return " ".join(value.split()) if value else None


def _add_dates(entry: dict[str, Any], lang: str, labels: dict[str, str]) -> None:
    start = entry.get("start")
    end = entry.get("end")
    entry["start_display"] = dates.display(start, lang, labels["present"])
    entry["end_display"] = dates.display(end, lang, labels["present"])
    entry["ongoing"] = end is None
    # Machine-readable, for HTML <time datetime="...">
    entry["start_iso"] = dates.iso(start)
    entry["end_iso"] = dates.iso(end)


# Which label a `grade_note` picks. Only the qualified notes appear here:
# 'final' and an absent note both mean a grade that stands on its own, and
# both fall through to the plain "Grade" / "Note".
_GRADE_LABEL = {
    "current": "grade_current",  # studies still running
    "preliminary": "grade_preliminary",  # degree obtained, final grade pending
}


def _education_meta(entry: dict[str, Any], labels: dict[str, str]) -> str | None:
    """Compose 'Thesis: X - Minor: Y - Current Grade 1.2', skipping absent parts.

    Built by collecting the present pieces and joining once, so an absent field
    can never leave a dangling separator.
    """
    parts: list[str] = []
    for key in ("thesis", "specialization", "minor"):
        value = _one_line(entry.get(key))
        if value:
            parts.append(f"{labels[key]}: {value}")

    grade = entry.get("grade")
    if grade:
        label = labels[_GRADE_LABEL.get(entry.get("grade_note"), "grade")]
        parts.append(f"{label} {grade}")

    return i18n.META_SEP.join(parts) if parts else None


def derive(data: dict[str, Any], lang: str, profile: str) -> dict[str, Any]:
    """Add everything the renderers would otherwise have to compute."""
    labels = i18n.labels(lang)
    data = clean(data)
    data["labels"] = labels
    data["meta"]["profile"] = profile

    # Ratings are opt-in per item; normalise both shapes to one so neither
    # renderer needs a branch for the shorthand.
    for group in data.get("skills", []):
        group["items"] = [_skill_item(item) for item in group["items"]]
    for entry in data.get("languages", []):
        entry.setdefault("rating", None)

    for entry in data.get("experience", []):
        _add_dates(entry, lang, labels)
        entry["meta_line"] = _one_line(entry.get("location"))

    for entry in data.get("education", []):
        _add_dates(entry, lang, labels)
        entry["meta_line"] = _education_meta(entry, labels)

    # Where the projects go is a layout choice, but it decides what the data
    # even contains, so it is resolved here rather than in either renderer.
    layout = data["meta"].get("projects_layout", "inline")
    data["meta"]["projects_layout"] = layout
    if layout == "omit":
        data.pop("projects", None)

    for entry in data.get("projects", []):
        _add_dates(entry, lang, labels)
        entry["meta_line"] = _one_line(entry.get("role"))
        entry.setdefault("image", None)
        entry["authors"] = [_author(author) for author in entry.get("authors", [])]
        if entry.get("url") and not entry.get("url_label"):
            entry["url_label"] = entry["url"].split("://", 1)[-1].rstrip("/")

    # Which sections actually have content, so main.typ does not need `if`s.
    data["sections"] = [
        name
        for name in (
            "profile",
            "experience",
            "education",
            "projects",
            "skills",
            "languages",
            "interests",
        )
        if data.get(name)
    ]
    # A projects *page* is not part of the main flow. Dropping it from
    # `sections` is what keeps main.typ free of layout conditionals: it renders
    # the list it is given, then asks once whether a projects page follows.
    if layout != "inline":
        data["sections"] = [name for name in data["sections"] if name != "projects"]
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def resolve(lang: str, profile: str = "full", *, quiet: bool = False) -> tuple[dict, list[str]]:
    """Run the whole pipeline in memory. Returns (resolved data, notes)."""
    if profile not in PROFILES:
        raise ResolveError(f"unknown profile {profile!r}, expected one of {', '.join(PROFILES)}")

    data = load_yaml(paths.source(lang))
    validate(data, lang)
    notes = merge_private(data, profile, quiet=quiet)
    return derive(data, lang, profile), notes


def write(lang: str, profile: str = "full", *, quiet: bool = False) -> Path:
    """Resolve and write build/cv-<lang>.json."""
    data, notes = resolve(lang, profile, quiet=quiet)
    target = paths.resolved(lang)
    target.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys keeps the diff readable if this ever gets committed for
    # debugging; list order - which is display order - is untouched.
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    target.write_text(text + "\n", encoding="utf-8")

    if not quiet:
        for note in notes:
            print(f"  note: {note}")
        rel = target.relative_to(paths.ROOT).as_posix()
        print(f"  wrote {rel}  (lang={lang}, profile={profile})")
    return target


def load_resolved(lang: str) -> dict[str, Any]:
    path = paths.resolved(lang)
    if not path.is_file():
        raise ResolveError(f"{path} not found - run `cvforge resolve --lang {lang}` first")
    return json.loads(path.read_text(encoding="utf-8"))
