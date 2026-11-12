"""`cvforge check` and `cvforge check-clean`.

`check` validates the data and reports content smells that are not errors -
a tag nobody lists as a skill is legitimate, just usually a typo.

`check-clean` is the cheap guard against a mis-set profile: it greps the
generated artifacts for the values in private.yaml. Publishing
out/cv-en.html to a website is a one-way action, so this exists to be run
before that, not after.
"""

from __future__ import annotations

import contextlib
import io
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from . import i18n, letter, paths, resolve

# Artifacts worth scanning as text. PDFs are compressed, so a literal grep
# would miss the string; they are handled separately below.
TEXT_SUFFIXES = {".json", ".html", ".css", ".txt", ".svg", ".md"}

# Roughly what fits on one line of the letter's subject at its type size.
SUBJECT_MAX = 78


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

    warnings += _check_letters()
    warnings += _check_dossiers()
    warnings += _check_documents()
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


def _check_letters() -> list[str]:
    """Validate every application's letter.yaml and report content smells.

    Validation failure raises, as it does for the CV - a letter that does not
    parse is not a warning. The smells are the ones you only notice after
    sending: an unedited template, a subject that will wrap, a contact row too
    long for the space above the address field.
    """
    out: list[str] = []
    for slug in _slugs():
        out += _check_letter(slug)
    return out


def _slugs() -> list[str]:
    """Every application directory, sorted; _template is a scaffold, not one."""
    if not paths.APPLICATIONS.is_dir():
        return []
    return sorted(
        p.name for p in paths.APPLICATIONS.iterdir() if p.is_dir() and not p.name.startswith("_")
    )


def check_application(slug: str) -> list[str]:
    """`check`'s warnings for one application only, without the progress lines.

    What a build of one application reports. Validation errors still raise.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        return _check_letter(slug) + _check_dossier(slug, set(_slugs()))


def _check_letter(slug: str) -> list[str]:
    out: list[str] = []
    src = paths.letter_source(slug)
    if not src.is_file():
        return [f"[{slug}] no letter.yaml in {paths.display(paths.application(slug))}"]

    print(f"checking {paths.display(src)}")
    data = resolve.load_yaml(src)
    letter.validate_letter(data, slug)  # raises ResolveError, caught by the CLI
    print("  schema ok")

    lang = data["meta"]["lang"]
    cv_src = paths.cv_source(lang, slug)
    if not cv_src.is_file():
        return [f"[{slug}] declares lang={lang!r} but {paths.display(cv_src)} is missing"]

    cv_data = resolve.load_yaml(cv_src)
    if cv_src != paths.source(lang):
        # A tailored CV gets the same validation as the base one, and the
        # checks for what would break its build. Not the tag check: it is a
        # copy, so that would only repeat the base CV's warnings per letter.
        print(f"checking {paths.display(cv_src)}")
        resolve.validate(cv_data, lang, cv_src)  # raises, like the base CV
        print("  schema ok")
        label = f"{slug}/cv.yaml"
        out += _check_photo(cv_data, label)
        out += _check_images(cv_data, label)
        out += _check_ids(cv_data, label)

    ids = {c["id"] for c in cv_data.get("contacts", [])}
    for cid in data.get("sender_contacts") or []:
        if cid not in ids:
            out.append(f"[{slug}] sender_contacts: no contact {cid!r} in {cv_src.name}")

    out += _check_attachments(data, slug, lang)

    for i, paragraph in enumerate(data.get("body") or []):
        if "TODO" in paragraph:
            out.append(f"[{slug}] body[{i}] still contains TODO")

    # The composed line, not just the title: the prefix and the reference
    # are most of what pushes it over, so measuring the title alone would
    # have missed exactly the cases this warning is for.
    subject = letter.subject_line(data, i18n.letter_labels(lang))
    if len(subject) > SUBJECT_MAX:
        out.append(
            f"[{slug}] the subject line is {len(subject)} characters; over about "
            f"{SUBJECT_MAX} it wraps onto a second line"
        )
    return out


# Text the scaffold used to ship as example values. Each one survived unedited
# in a real dossier and was later read as a fact - a recruiter who does not
# exist, an application date nobody chose.
TEMPLATE_REMNANTS = (
    "Anna Beispiel",
    "Anything else worth remembering.",
    "What they actually ask for, in your own words.",
)
# The old scaffold's timeline entry. Matched as a whole: "applied via the
# company portal" is a fine thing to write yourself - with your own date.
TEMPLATE_TIMELINE = {"date": "2026-09-08", "event": "Applied via the company portal"}

# A status that means the application went out, so `applied` must say when.
SENT = frozenset({"applied", "screening", "interview", "offer", "rejected"})


def _check_dossiers() -> list[str]:
    """Validate every dossier.yaml and report what makes it useless later.

    A dossier is read weeks after it was written - before an interview, or by
    `cvforge list` when a similar job comes up - so the smells are the ones
    that mislead then: leftover template text, no summary to match on, a
    status that says "applied" with no date.
    """
    out: list[str] = []
    slugs = set(_slugs())
    for slug in sorted(slugs):
        out += _check_dossier(slug, slugs)
    return out


def _check_dossier(slug: str, slugs: set[str]) -> list[str]:
    src = paths.dossier(slug)
    if not src.is_file():
        return [f"[{slug}] no dossier.yaml"]

    print(f"checking {paths.display(src)}")
    data = resolve.load_yaml(src)
    resolve.validate_against(data, paths.DOSSIER_SCHEMA, paths.display(src))
    print("  schema ok")

    out: list[str] = []
    raw = src.read_text(encoding="utf-8")
    for remnant in TEMPLATE_REMNANTS:
        if remnant in raw:
            out.append(f"[{slug}] dossier.yaml still contains template text {remnant!r}")
    if TEMPLATE_TIMELINE in (data.get("timeline") or []):
        out.append(
            f"[{slug}] timeline still has the template entry "
            f"{TEMPLATE_TIMELINE['date']} {TEMPLATE_TIMELINE['event']!r}"
        )

    if not data.get("summary") or not data.get("keywords"):
        out.append(
            f"[{slug}] dossier.yaml has no summary or keywords - "
            f"`cvforge list --match` cannot find it"
        )

    status, applied = data.get("status"), data.get("applied")
    if status in SENT and not applied:
        out.append(f"[{slug}] status is {status!r} but `applied` has no date")
    if applied and status in (None, "draft"):
        out.append(f"[{slug}] `applied` is {applied} but status is still {status!r}")

    posting_data = data.get("posting") or {}
    archive = posting_data.get("archive")
    if archive and not (paths.application(slug) / archive).is_file():
        out.append(
            f"[{slug}] posting.archive {archive!r} does not exist "
            f"(it is relative to the application directory)"
        )
    if archive and not posting_data.get("fetched"):
        out.append(f"[{slug}] posting.archive is set but posting.fetched has no date")
    archived = sorted(
        p.name for p in (paths.application(slug) / "posting").glob("*") if p.is_file()
    )
    if archived and not archive:
        # A posting dropped into the folder by hand is invisible to whoever
        # reads only the dossier - which is how it was once reported missing.
        out.append(f"[{slug}] posting/ holds {', '.join(archived)} but posting.archive is null")

    based_on = (data.get("approach") or {}).get("based_on")
    if based_on and based_on not in slugs:
        out.append(f"[{slug}] approach.based_on names no application {based_on!r}")
    return out + _check_timeline(slug, data)


def _check_timeline(slug: str, data: dict[str, Any]) -> list[str]:
    """What breaks the links the dashboard draws: a participant who is not a
    contact, a track that does not exist - and a planned entry whose day has
    passed, which is an interview nobody wrote down."""
    out: list[str] = []
    names = {c["name"] for c in data.get("contacts") or []}
    track_ids = [t["id"] for t in data.get("tracks") or []]
    for tid in sorted({t for t in track_ids if track_ids.count(t) > 1}):
        out.append(f"[{slug}] tracks: id {tid!r} is used more than once")

    today = date.today().isoformat()
    for entry in data.get("timeline") or []:
        label = f"[{slug}] timeline {entry['date']} {_clip(entry['event'])!r}"
        for name in entry.get("with") or []:
            if name not in names:
                out.append(f"{label}: {name!r} is not in contacts")
        track = entry.get("track")
        if track and track not in track_ids:
            out.append(f"{label}: no track {track!r}")
        for rel in entry.get("files") or []:
            if not (paths.application(slug) / rel).is_file():
                out.append(f"{label}: file {rel!r} does not exist")
        if entry.get("planned") and entry["date"] < today:
            out.append(f"{label} was planned and its day has passed - what happened?")
    return out


def _clip(text: str, width: int = 40) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _document_pool() -> dict[str, Any]:
    """The `documents:` declarations from private.yaml, keyed by id."""
    if not paths.PRIVATE.is_file():
        return {}
    return {
        entry["id"]: entry
        for entry in resolve.load_yaml(paths.PRIVATE).get("documents") or []
        if isinstance(entry, dict) and entry.get("id")
    }


def _check_documents() -> list[str]:
    """Warn once per declared document file that is not on disk.

    Deliberately separate from the per-letter check: a document is declared
    once, so a missing scan is one problem, not one problem per application
    that attaches it. Five letters citing the same missing transcript should
    not produce five identical warnings.
    """
    out: list[str] = []
    for did, entry in sorted(_document_pool().items()):
        named = letter._declared_files(entry.get("file", ""))
        if not named:
            out.append(f"[documents] {did}: declares no usable `file:`")
            continue
        for rel in named:
            if not paths.private_path(rel).is_file():
                out.append(f"[documents] {did}: {rel} does not exist")
    return out


def _check_attachments(data: dict[str, Any], slug: str, lang: str) -> list[str]:
    """Warn about an attachment this letter cannot resolve.

    File existence for the shared pool is _check_documents' job, once. What is
    per-letter is whether the id resolves at all, whether the edition this
    letter's language needs was declared, and whether a one-off file - which
    belongs to this application and nothing else - is there.
    """
    listed = data.get("attachments") or []
    if not listed:
        return []

    pool = _document_pool()
    out: list[str] = []
    for i, entry in enumerate(listed):
        if isinstance(entry, str):
            declared = pool.get(entry)
            if declared is None:
                out.append(
                    f"[{slug}] attachments[{i}]: no document {entry!r} declared "
                    f"in {letter.PRIVATE_NAME}"
                )
                continue
            declared_file = declared.get("file", "")
            if isinstance(declared_file, dict) and not declared_file.get(lang):
                out.append(
                    f"[{slug}] attachments[{i}]: {entry!r} has language-specific "
                    f"editions but none for {lang} - another language's will be sent"
                )
        elif isinstance(entry, dict):
            source = paths.application(slug) / entry.get("file", "")
            if not source.is_file():
                out.append(f"[{slug}] attachments[{i}]: {paths.display(source)} does not exist")
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


# Top-level keys in private.yaml that are a manifest of secrets rather than
# secrets themselves. `signature` and `documents` name gitignored files; those
# paths and labels are written into build/letter-<slug>.json by design, and
# "Masterzeugnis" is printed in the Anlagen line of the letter itself. Scanning
# for them would report a leak on every letter build, and a check that always
# cries wolf is a check nobody reads. What must not be published is the file
# each one points at, and .gitignore is what guarantees that.
NOT_SECRET = frozenset({"signature", "documents"})


def _public_text() -> str:
    """Everything the committed CV data already says, as one blob."""
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(paths.DATA.glob("cv-*.yaml"))
    )


def _private_needles() -> list[tuple[str, str]]:
    """Every leaf string in private.yaml, plus a digits-only phone variant.

    The digits-only form catches a renderer that reformatted the number, e.g.
    "+49 721 1234567" written into a tel: URL as "+491234567".

    Values that the committed data/cv-*.yaml already contain are dropped. A
    value that is public by construction cannot be leaked by publishing it, and
    private.yaml legitimately holds some: the structured `address` block
    repeats the city, which the CV publishes as "Karlsruhe, DE". Without this
    filter `export` would find that in the public site JSON, call it a leak and
    refuse to publish the website.
    """
    needles: list[tuple[str, str]] = []

    def walk(node: Any, trail: str) -> None:
        # Match on the first path segment, so a whole subtree is covered:
        # "documents" also skips "documents[0].file" and "documents[0].label".
        if trail.split(".")[0].split("[")[0] in NOT_SECRET:
            return
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

    # A needle shorter than this matches something innocent sooner or later,
    # and nothing that short is worth protecting on its own.
    public = _public_text()
    return [(trail, value) for trail, value in needles if len(value) >= 4 and value not in public]


def check_clean(targets: tuple[Path, ...] = (paths.BUILD, paths.OUT)) -> int:
    """Fail if any private value reached the generated artifacts.

    Each target may be a directory to walk or a single file. `export` passes
    the exact files it just wrote, so its report does not sweep in unrelated
    documents that happen to share the website's static/files directory.
    """
    if not paths.PRIVATE.is_file():
        print(f"no {letter.PRIVATE_NAME} - nothing to check")
        return 0

    needles = _private_needles()
    if not needles:
        print(f"{letter.PRIVATE_NAME} has no values - nothing to check")
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
