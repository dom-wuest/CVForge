"""`cvforge check` and `cvforge check-clean`.

`check` validates the data and reports content smells that are not errors -
a tag nobody lists as a skill is legitimate, just usually a typo.

`check-clean` is the cheap guard against a mis-set profile: it greps the
generated artifacts for the values in data/private.yaml. Publishing
out/cv-en.html to a website is a one-way action, so this exists to be run
before that, not after.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from . import i18n, paths, resolve

# Artifacts worth scanning as text. PDFs are compressed, so a literal grep
# would miss the string; they are handled separately below.
TEXT_SUFFIXES = {".json", ".html", ".css", ".txt", ".svg", ".md"}


def check(langs: tuple[str, ...] = i18n.LANGS) -> int:
    """Validate every language file present and report warnings. Returns exit code."""
    warnings: list[str] = []
    checked = 0

    for lang in langs:
        src = paths.source(lang)
        if not src.is_file():
            continue
        checked += 1
        print(f"checking {src.relative_to(paths.ROOT).as_posix()}")

        data = resolve.load_yaml(src)
        resolve.validate(data, lang)  # raises ResolveError, caught by the CLI
        print("  schema ok")

        warnings += _check_tags(data, lang)
        warnings += _check_photo(data, lang)
        warnings += _check_images(data, lang)
        warnings += _check_ids(data, lang)

    if not checked:
        print("no data/cv-*.yaml files found")
        return 1

    warnings += _check_private_coverage(langs)

    if warnings:
        print()
        for w in warnings:
            print(f"  warning: {w}")
        print(f"\n{len(warnings)} warning(s). These are advisory - nothing failed.")
    else:
        print("\nno warnings")
    return 0


def _check_tags(data: dict[str, Any], lang: str) -> list[str]:
    """Warn when an entry tag appears in no skills group.

    Per-entry tags are legitimately more granular than the skills section, so
    this is a nudge about typos, never an error.

    Education is excluded: its tags are study focus areas ("Computer Graphics",
    "Anthropomatics and Cognitive Systems"), a different vocabulary from the
    skills list. Checking them would emit warnings that can never be resolved,
    which trains you to ignore the ones that matter.
    """
    # Raw YAML shape here, before resolve normalises it, so an item is either
    # a bare string or a mapping with a name. Group names count too: tagging a
    # project "Machine Learning" is legitimate even though that is a heading
    # rather than a listed item.
    known = {
        (item if isinstance(item, str) else item["name"]).casefold()
        for group in data.get("skills", [])
        for item in group["items"]
    }
    known |= {group["group"].casefold() for group in data.get("skills", [])}
    out = []
    for section in ("experience", "projects"):
        for entry in data.get(section, []):
            for tag in entry.get("tags", []):
                if tag.casefold() not in known:
                    out.append(
                        f"[{lang}] {section}.{entry['id']}: tag {tag!r} is in no skills group"
                    )
    return out


def _check_photo(data: dict[str, Any], lang: str) -> list[str]:
    photo = data["meta"].get("photo")
    if photo and not (paths.ROOT / photo).is_file():
        return [f"[{lang}] meta.photo points at {photo}, which does not exist"]
    return []


def _check_images(data: dict[str, Any], lang: str) -> list[str]:
    """A missing screenshot is a hard Typst error, so catch it here first."""
    out = []
    for entry in data.get("projects", []):
        picture = entry.get("image")
        if picture and not (paths.ROOT / picture).is_file():
            out.append(f"[{lang}] projects.{entry['id']}: image {picture} does not exist")
    return out


def _check_ids(data: dict[str, Any], lang: str) -> list[str]:
    out = []
    for section in ("contacts", "experience", "education", "projects"):
        seen: set[str] = set()
        for entry in data.get(section, []):
            eid = entry["id"]
            if eid in seen:
                out.append(f"[{lang}] {section}: duplicate id {eid!r}")
            seen.add(eid)
    return out


def _check_private_coverage(langs: tuple[str, ...]) -> list[str]:
    """Warn about contacts marked private with no matching private.yaml entry."""
    if not paths.PRIVATE.is_file():
        return []
    overrides = set(resolve.load_yaml(paths.PRIVATE).get("contacts") or {})
    out = []
    for lang in langs:
        src = paths.source(lang)
        if not src.is_file():
            continue
        for contact in resolve.load_yaml(src).get("contacts", []):
            if contact.get("private") and contact["id"] not in overrides:
                out.append(
                    f"[{lang}] contact {contact['id']!r} is marked private "
                    f"but private.yaml has no entry for it - the placeholder will be used"
                )
    return out


# ─────────────────────────────────────────────────────────────────────────────


def _private_needles() -> list[tuple[str, str]]:
    """Every leaf string in private.yaml, plus a digits-only phone variant.

    The digits-only form catches a renderer that reformatted the number, e.g.
    "+49 721 1234567" written into a tel: URL as "+491234567".
    """
    needles: list[tuple[str, str]] = []

    def walk(node: Any, trail: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{trail}.{k}" if trail else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{trail}[{i}]")
        elif isinstance(node, str) and node.strip():
            needles.append((trail, node.strip()))

    walk(yaml.safe_load(paths.PRIVATE.read_text(encoding="utf-8")) or {}, "")

    for trail, value in list(needles):
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 7:
            needles.append((f"{trail} (digits only)", digits))
    return needles


def check_clean(targets: tuple[Path, ...] = (paths.BUILD, paths.OUT)) -> int:
    """Fail if any private value reached the generated artifacts.

    Each target may be a directory to walk or a single file. `export` passes
    the exact files it just wrote, so its report does not sweep in unrelated
    documents that happen to share the website's static/files directory.
    """
    if not paths.PRIVATE.is_file():
        print("no data/private.yaml - nothing to check")
        return 0

    needles = _private_needles()
    if not needles:
        print("data/private.yaml has no values - nothing to check")
        return 0

    scanned = 0
    hits: list[str] = []
    skipped_binary: list[str] = []

    candidates: list[Path] = []
    for target in targets:
        if target.is_file():
            candidates.append(target)
        elif target.is_dir():
            candidates += sorted(p for p in target.rglob("*") if p.is_file())

    for path in candidates:
        rel = paths.display(path)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            skipped_binary.append(rel)
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for trail, needle in needles:
            if needle in text:
                hits.append(f"{rel}: contains private value from {trail}")

    print(f"scanned {scanned} text artifact(s) for {len(needles)} private value(s)")

    if skipped_binary:
        # Say what was not covered rather than implying full coverage. A PDF is
        # compressed, so a literal grep cannot see inside one. Under
        # profile=full it is *supposed* to carry the phone number; under
        # profile=public `export` guarantees it differently, by asserting the
        # artifact it renders from is public before Typst ever runs.
        print("not scanned (compressed; a literal grep cannot see inside a PDF):")
        for rel in skipped_binary:
            print(f"  {rel}")

    if hits:
        print()
        for hit in hits:
            print(f"  LEAK  {hit}")
        print(f"\n{len(hits)} leak(s). Rebuild with --profile public before publishing.")
        return 1

    print("clean")
    return 0
