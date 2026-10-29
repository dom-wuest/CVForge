"""What the commands do, as functions that return their results.

The CLI and the MCP server both call these, so the two cannot drift apart: one
`apply`, one `new`, one notion of "sent". Progress lines are still printed -
the CLI shows them, the MCP server captures them - but everything a caller
needs to decide on comes back as data.

Typst runs with its output captured and re-printed rather than inherited. On
an MCP stdio connection, stdout *is* the protocol; a subprocess writing to it
directly would corrupt the stream, and redirecting `sys.stdout` in Python does
not reach a child process.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import check as check_mod
from . import home as home_mod
from . import letter, paths, resolve

# ─────────────────────────────────────────────────────────────────────────────
# Typst
# ─────────────────────────────────────────────────────────────────────────────


def typst() -> str:
    exe = shutil.which("typst")
    if exe is None:
        raise resolve.ResolveError(
            "typst not found on PATH. Install it from https://github.com/typst/typst/releases "
            "or `winget install Typst.Typst`."
        )
    return exe


def typst_version() -> str | None:
    try:
        result = subprocess.run([typst(), "--version"], capture_output=True, text=True)
    except resolve.ResolveError:
        return None
    return result.stdout.strip() or None


def page_count(pdf: Path) -> int | None:
    """Page count of a PDF we just produced, or None if it cannot be read.

    One page is a design requirement here, and the German CV has only a few
    millimetres of slack, so a silent regression to two pages is easy to ship
    unnoticed. This reads /Count out of the page tree rather than taking on a
    PDF dependency.

    It only ever parses our own Typst output, which writes the page tree as
    "<</Type/Pages/Count 1/Kids[...]>>". Anything else returns None and the
    caller simply omits the number - this must never fail a build. The search
    is anchored on the /Pages type because /Count also appears in the outline.

    The whitespace in the pattern is not decorative: PDF allows a space between
    a key and its value, and typst 0.14 emits "/Type /Pages" where 0.13 emitted
    "/Type/Pages". Matching only the tight form made this return None on every
    build - which is invisible, because None just omits the number.
    """
    try:
        blob = pdf.read_bytes()
    except OSError:
        return None
    found = re.search(rb"/Type\s*/Pages\b", blob)
    if found is None:
        return None
    key = re.compile(rb"/Count\s*(\d+)").search(blob, found.end(), found.end() + 200)
    return int(key.group(1)) if key else None


def _typst_args(main: Path, inputs: dict[str, str]) -> list[str]:
    args = [
        "--root",
        ".",
        "--font-path",
        str(paths.FONTS.relative_to(paths.ROOT)),
    ]
    for key, value in inputs.items():
        args += ["--input", f"{key}={value}"]
    return args


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run typst with its output captured, then pass it on via sys.stdout/stderr."""
    result = subprocess.run(
        cmd, cwd=paths.ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result


def compile_typst(main: Path, target: Path, inputs: dict[str, str]) -> int | None:
    """Run typst with the flags this project always needs. Returns the page count.

    --root .            so a template can read /build/<artifact>.json by absolute path
    --font-path         so Font Awesome resolves; without it icons come out blank
                        and the body text silently falls back to another typeface
    --input k=v         so one template serves every language, and every letter

    --root only constrains what Typst may *read*, so an output outside the repo
    is fine - that is how `export` writes into the website's working copy.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_arg = str(target.relative_to(paths.ROOT))
    except ValueError:
        out_arg = str(target)
    cmd = [typst(), "compile", str(main.relative_to(paths.ROOT)), out_arg]
    cmd += _typst_args(main, inputs)

    print("  " + " ".join(cmd[1:]))
    result = _run(cmd)
    if result.returncode != 0:
        raise resolve.ResolveError(f"typst compile failed (exit {result.returncode})")

    pages = page_count(target)
    suffix = "" if pages is None else f"  ({pages} page{'s' if pages != 1 else ''})"
    print(f"  wrote {paths.display(target)}{suffix}")
    return pages


def compile_cv(lang: str, target: Path | None = None, artifact: Path | None = None) -> int | None:
    """Compile the CV. Returns the page count.

    `target` defaults to out/cv-<lang>.pdf. `export` passes a path in the
    website's working copy instead, so the public PDF never lands in out/ and
    overwrites the full-profile one you send with applications.

    `artifact` is a resolved CV other than build/cv-<lang>.json - an
    application's tailored copy. main.typ reads it by root-absolute path.
    """
    target = paths.pdf(lang) if target is None else target
    return compile_typst(paths.CV_MAIN, target, _cv_inputs(lang, artifact))


def _cv_inputs(lang: str, artifact: Path | None) -> dict[str, str]:
    inputs = {"lang": lang}
    if artifact is not None:
        inputs["artifact"] = "/" + artifact.relative_to(paths.ROOT).as_posix()
    return inputs


def compile_letter(slug: str, lang: str, target: Path) -> int | None:
    """Compile one cover letter, and complain if it did not come out on one page.

    A two-page cover letter is a content problem, not a layout one - nobody
    reads the second page - so this is loud but not fatal: you may well be
    mid-edit, and failing the build would only get in the way.
    """
    pages = compile_typst(paths.LETTER_MAIN, target, {"slug": slug, "lang": lang})
    if pages is not None and pages > 1:
        print(
            f"  warning: the letter is {pages} pages. A cover letter is one page - "
            f"cut a paragraph, or trim `sender_contacts` if the letterhead is "
            f"crowding the address field.",
            file=sys.stderr,
        )
    return pages


def expected_cv_pages(cv: dict) -> int:
    """How many pages a CV that has not overflowed comes out at.

    One, plus the projects page when `projects_layout: page` gives projects one
    of their own. More than this means the main page overflowed - the symptom
    is a stub of the sidebar rule on the next page.
    """
    return 2 if cv["meta"].get("projects_layout") == "page" else 1


def pages_label(count: int | None) -> str:
    if count is None:
        return "? pages"
    return f"{count} page{'s' if count != 1 else ''}"


# ─────────────────────────────────────────────────────────────────────────────
# Layout report
# ─────────────────────────────────────────────────────────────────────────────
# The templates leave `cvforge-*` metadata where the flow ended (see
# templates/pdf/components/marker.typ). Reading it back says how much room a
# build has, in millimetres - which is how an overflow can be fixed by someone
# who never sees the page.

LETTER_MARKERS = ("cvforge-letter-end", "cvforge-letterhead")
CV_MARKERS = ("cvforge-main-end", "cvforge-aside-end", "cvforge-projects-end")


def _markers(main: Path, inputs: dict[str, str], names: tuple[str, ...]) -> dict[str, list]:
    fields = ", ".join(f'"{n}": query(<{n}>).map(it => it.value)' for n in names)
    cmd = [typst(), "eval", f"({fields})", "--in", str(main.relative_to(paths.ROOT))]
    cmd += _typst_args(main, inputs)
    result = subprocess.run(
        cmd, cwd=paths.ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def _flow(marker: dict | None, expected_page: int) -> dict[str, Any] | None:
    """Where a flow ended, relative to where it should have."""
    if not marker:
        return None
    report: dict[str, Any] = {"ends_on_page": marker["page"]}
    if marker["page"] <= expected_page:
        report["room_mm"] = round(marker["limit_mm"] - marker["y_mm"], 1)
    else:
        # Spilled: how far it ran into the next page is how much must go.
        report["overflow_mm"] = round(marker["y_mm"] - marker["top_mm"], 1)
    return report


def letter_layout(slug: str, lang: str) -> dict[str, Any]:
    found = _markers(paths.LETTER_MAIN, {"slug": slug, "lang": lang}, LETTER_MARKERS)
    end = (found.get("cvforge-letter-end") or [None])[-1]
    head = (found.get("cvforge-letterhead") or [None])[0]
    report: dict[str, Any] = {"body": _flow(end, 1)}
    if head:
        report["letterhead"] = {
            "height_mm": round(head["height_mm"], 1),
            "budget_mm": round(head["budget_mm"], 1),
            "room_mm": round(head["budget_mm"] - head["height_mm"], 1),
        }
    return report


def cv_layout(lang: str, artifact: Path | None, expected: int) -> dict[str, Any]:
    found = _markers(paths.CV_MAIN, _cv_inputs(lang, artifact), CV_MARKERS)
    report = {
        "main_column": _flow((found.get("cvforge-main-end") or [None])[-1], 1),
        "sidebar": _flow((found.get("cvforge-aside-end") or [None])[-1], 1),
    }
    projects = (found.get("cvforge-projects-end") or [None])[-1]
    if projects:
        report["projects_page"] = _flow(projects, expected)
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Applications
# ─────────────────────────────────────────────────────────────────────────────


def slugify_name(name: str) -> str:
    """A person's name as a filename an employer's system will not mangle.

    "Dominik Wüst" -> "Dominik_Wuest". Transliterating rather than stripping,
    because "Wst" is worse than either.
    """
    folded = name
    for source, target in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        folded = folded.replace(source, target).replace(source.upper(), target.capitalize())
    # Apostrophes vanish rather than becoming separators: a document label like
    # "Bachelor's Degree Certificate" should read Bachelors_Degree_Certificate,
    # not Bachelor_s_Degree_Certificate.
    folded = folded.replace("'", "").replace("’", "")
    ascii_only = unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", ascii_only).strip("_")


def send_name(index: int, stem: str, label: str, suffix: str) -> str:
    """One file in the send-ready folder: "01_Dominik_Wuest_Anschreiben.pdf".

    The numeric prefix is what makes the folder sort in the order the letter
    lists things, in every file dialog and every upload form. Alphabetical
    order only matches what an employer expects by luck - "Arbeitszeugnis"
    sorts before "Anschreiben".
    """
    return f"{index:02d}_{stem}_{slugify_name(label)}{suffix}"


def clear_bundle(out: Path) -> None:
    """Empty the send folder before refilling it.

    Without this, dropping an attachment from the letter leaves the old file
    behind and you send it anyway - the exact failure this command exists to
    prevent. Only ever the one application's send/ folder, which nothing but
    `apply` writes to, and only the files directly in it - never a directory,
    never anything beside it.
    """
    if not out.is_dir():
        return
    stale = [p for p in out.iterdir() if p.is_file()]
    for path in stale:
        path.unlink()
    if stale:
        print(f"  cleared {len(stale)} stale file(s) from {paths.display(out)}")


def load_dossier(slug: str) -> dict[str, Any]:
    src = paths.dossier(slug)
    return resolve.load_yaml(src) if src.is_file() else {}


def sent_on(slug: str) -> str | None:
    """Why the dossier says this application went out, or None if it did not."""
    dossier = load_dossier(slug)
    if dossier.get("applied"):
        return f"applied {dossier['applied']}"
    if dossier.get("status") in check_mod.SENT:
        return f"status {dossier['status']}"
    return None


def refuse_if_sent(slug: str, what: str) -> None:
    sent = sent_on(slug)
    if sent:
        raise resolve.ResolveError(
            f"{slug} was sent ({sent}), so {what} would change the record of what the "
            f"employer received."
        )


@dataclass
class ApplyResult:
    slug: str
    folder: Path
    letter_pages: int | None
    cv_pages: int | None
    expected_cv_pages: int
    cv_source: Path
    files: list[str] = field(default_factory=list)
    attachments: int = 0

    def summary_line(self) -> str:
        """The fixed-format line the /new-application skill parses. Keep it stable."""
        return (
            f"summary: letter {pages_label(self.letter_pages)} | "
            f"cv {pages_label(self.cv_pages)} (expected {self.expected_cv_pages}) | "
            f"cv source {paths.display(self.cv_source)} | "
            f"{self.attachments} attachment{'s' if self.attachments != 1 else ''}"
        )


def _resolved_cv(slug: str, lang: str) -> tuple[Path, Path, bool]:
    """(cv source, resolved artifact, tailored?) for this application's CV."""
    cv_source = paths.cv_source(lang, slug)
    tailored = cv_source != paths.source(lang)
    cv_json = resolve.write(
        lang,
        "full",
        quiet=True,
        source=cv_source,
        target=paths.cv_resolved_for(slug) if tailored else None,
    )
    return cv_source, cv_json, tailored


def apply_application(slug: str, *, force: bool = False) -> ApplyResult:
    """Build the whole send-ready folder: letter, CV, and every attachment.

    The CV is rebuilt here rather than reused from out/ so the two documents in
    the folder are guaranteed to be the same vintage, and in the same language
    as the letter. Both are profile=full - this folder is for an employer, not
    for the web.

    The CV is the one the letter's sender block came from (`meta.cv_source`):
    the application's tailored cv.yaml if it has one, else data/cv-<lang>.yaml.
    A tailored CV resolves to its own build/cv-app-<slug>.json, never over the
    base CV's artifact.

    Refuses, unless `force`, once the dossier says the application went out:
    send/ is then the record of what the employer received, and a rebuild
    would replace it with what the sources produce today.
    """
    sent = sent_on(slug)
    if sent and not force:
        raise resolve.ResolveError(
            f"{slug} was sent ({sent}), so {paths.display(paths.bundle(slug))} "
            f"holds what the employer received. Rebuilding would replace it.\n"
            f"  Use `cvforge letter {slug}` to look at a draft, or `apply --force` "
            f"if you really mean to rebuild the folder."
        )

    letter.write_letter(slug)
    artifact = json.loads(paths.letter_resolved(slug).read_text(encoding="utf-8"))
    lang = artifact["meta"]["lang"]
    labels = artifact["labels"]
    stem = slugify_name(artifact["meta"]["name"])
    attached = artifact.get("attachments", [])

    # Refuse before writing anything. A folder with a hole in it is worse than
    # no folder at all: the point of this command is that you can send what it
    # produced without checking it first. Every problem at once, so fixing them
    # is one round trip rather than five.
    unresolved = [a["label"] for a in attached if not a.get("file")]
    if unresolved:
        raise resolve.ResolveError(
            "these attachments have no file, so the folder was not built: "
            + ", ".join(unresolved)
            + f"\n  Check `documents:` in {letter.PRIVATE_NAME}, and that each `file:` exists."
        )

    out = paths.bundle(slug)
    clear_bundle(out)

    print(f"[{slug}] letter")
    letter_file = out / send_name(1, stem, labels["file_letter"], ".pdf")
    letter_pages = compile_letter(slug, lang, letter_file)

    # The same decision the letter's sender block was resolved from a moment
    # ago (`meta.cv_source` records it). Asked again rather than parsed back
    # out of the artifact, because a tailored CV in the home is an absolute
    # path there, not a repo-relative one.
    cv_source, cv_json, tailored = _resolved_cv(slug, lang)
    print(f"[{slug}] cv ({lang}, {paths.display(cv_source)})")
    cv_file = out / send_name(2, stem, labels["file_cv"], ".pdf")
    cv_pages = compile_cv(lang, target=cv_file, artifact=cv_json if tailored else None)
    expected = expected_cv_pages(json.loads(cv_json.read_text(encoding="utf-8")))
    if cv_pages is not None and cv_pages != expected:
        print(
            f"  warning: the CV is {pages_label(cv_pages)}, expected {expected} - it "
            f"overflowed. Shorten {paths.display(cv_source)}, or see 'Fitting on one "
            f"page' in CLAUDE.md.",
            file=sys.stderr,
        )

    files = [letter_file.name, cv_file.name]
    if attached:
        print(f"[{slug}] attachments")
        for i, entry in enumerate(attached, start=3):
            source = Path(entry["file"])
            target = out / send_name(i, stem, entry["label"], source.suffix.lower())
            shutil.copyfile(source, target)
            files.append(target.name)
            print(f"  wrote {paths.display(target)}")

    return ApplyResult(
        slug=slug,
        folder=out,
        letter_pages=letter_pages,
        cv_pages=cv_pages,
        expected_cv_pages=expected,
        cv_source=cv_source,
        files=files,
        attachments=len(attached),
    )


@dataclass
class DraftResult:
    slug: str
    letter_pages: int | None
    cv_pages: int | None
    expected_cv_pages: int
    cv_source: Path
    letter_layout: dict[str, Any]
    cv_layout: dict[str, Any]
    warnings: list[str]


def build_draft(slug: str) -> DraftResult:
    """Letter and CV into out/ - never send/ - with the layout report.

    The loop while fitting a page: it may run any number of times, before or
    after sending, because nothing it writes is a record of anything.
    """
    letter.write_letter(slug)
    artifact = json.loads(paths.letter_resolved(slug).read_text(encoding="utf-8"))
    lang = artifact["meta"]["lang"]
    letter_pages = compile_letter(slug, lang, paths.letter_pdf(slug))

    cv_source, cv_json, tailored = _resolved_cv(slug, lang)
    cv_artifact = cv_json if tailored else None
    cv_pages = compile_cv(lang, target=paths.draft_cv_pdf(slug), artifact=cv_artifact)
    expected = expected_cv_pages(json.loads(cv_json.read_text(encoding="utf-8")))

    return DraftResult(
        slug=slug,
        letter_pages=letter_pages,
        cv_pages=cv_pages,
        expected_cv_pages=expected,
        cv_source=cv_source,
        letter_layout=letter_layout(slug, lang),
        cv_layout=cv_layout(lang, cv_artifact, expected),
        warnings=check_mod.check_application(slug),
    )


def new_application(
    slug: str, lang: str, *, tailored_cv: bool = False, from_slug: str | None = None
) -> list[Path]:
    """Scaffold applications/<slug>/. Returns the files written.

    With `from_slug`, the letter and (if it had one) the tailored CV start as
    copies of that earlier application rather than of the scaffold and the base
    CV - the structure that worked for a similar job, ready to be adapted. The
    dossier still starts empty apart from `approach.based_on`; its facts belong
    to the other job.
    """
    target = paths.application(slug)
    if target.exists():
        raise resolve.ResolveError(f"{paths.display(target)} already exists")
    if not paths.APPLICATION_TEMPLATE.is_dir():
        raise resolve.ResolveError(f"missing scaffold: {paths.display(paths.APPLICATION_TEMPLATE)}")

    base = paths.source(lang)
    origin_letter = origin_cv = None
    if from_slug:
        origin_letter = paths.letter_source(from_slug)
        if not origin_letter.is_file():
            raise resolve.ResolveError(f"--from: {paths.display(origin_letter)} does not exist")
        origin_lang = resolve.load_yaml(origin_letter)["meta"]["lang"]
        if origin_lang != lang:
            raise resolve.ResolveError(
                f"--from: {from_slug} is a {origin_lang!r} application; its letter cannot "
                f"start a {lang!r} one. Use --lang {origin_lang}, or start without --from."
            )
        if paths.cv_override(from_slug).is_file():
            origin_cv = paths.cv_override(from_slug)
    cv_from = origin_cv or base
    if (tailored_cv or origin_cv) and not cv_from.is_file():
        raise resolve.ResolveError(f"--cv: {paths.display(cv_from)} does not exist")

    target.mkdir(parents=True)
    written: list[Path] = []
    # The `$schema=../../schema/` hints below resolve against this in a home.
    home_mod.sync_schema()

    if origin_letter:
        text = origin_letter.read_text(encoding="utf-8")
        text = re.sub(r"^(\s+slug:).*$", rf"\1 {slug}", text, count=1, flags=re.MULTILINE)
        text = re.sub(r"^(\s+date:).*$", r"\1 null", text, count=1, flags=re.MULTILINE)
    else:
        text = (paths.APPLICATION_TEMPLATE / "letter.yaml").read_text(encoding="utf-8")
        text = text.replace("slug: new-application", f"slug: {slug}")
        text = text.replace("lang: de", f"lang: {lang}")
    letter_file = paths.letter_source(slug)
    letter_file.write_text(text, encoding="utf-8")
    written.append(letter_file)

    # dossier.yaml is never committed; the example it comes from is.
    example = paths.APPLICATION_TEMPLATE / "dossier.example.yaml"
    if example.is_file():
        # The one fact known now: the day it was started. `cvforge list` falls
        # back to it for an application that has not been sent yet.
        created = f'timeline:\n  - date: "{date.today().isoformat()}"\n    event: "Created"\n'
        text = example.read_text(encoding="utf-8")
        text = re.sub(r"^timeline: \[\].*\n", created, text, count=1, flags=re.MULTILINE)
        if from_slug:
            text = re.sub(
                r"^(\s+based_on:).*$", rf"\1 {from_slug}", text, count=1, flags=re.MULTILINE
            )
        dossier_file = paths.dossier(slug)
        dossier_file.write_text(text, encoding="utf-8")
        written.append(dossier_file)

    # A CV tailored to this application: a full copy, so it is a snapshot of
    # what was sent and later edits to the base CV do not reach back into it.
    # The base CV also feeds the website, which is why tailoring happens here.
    if tailored_cv or origin_cv:
        text = cv_from.read_text(encoding="utf-8")
        if cv_from == base:
            # One directory deeper than data/, so the schema hint needs one more ../
            text = text.replace("$schema=../schema/", "$schema=../../schema/", 1)
        origin = f"{from_slug}/cv.yaml" if origin_cv else paths.display(cv_from)
        header = (
            f"# Tailored copy of {origin}, taken {date.today().isoformat()}.\n"
            f"# For this application alone: `cvforge letter` and `apply` use it\n"
            f"# instead of the base CV, and edits here never reach the website.\n"
            f"# private.yaml is still merged in, exactly as for the base CV.\n"
        )
        first, _, rest = text.partition("\n")
        if cv_from != base:
            # Drop the copied header so the file names one origin, not a chain.
            rest = re.sub(r"\A(#[^\n]*\n)+", "", rest)
        if first.startswith("# yaml-language-server:"):
            text = f"{first}\n#\n{header}{rest}"
        else:
            text = header + text
        cv_file = paths.cv_override(slug)
        cv_file.write_text(text, encoding="utf-8")
        written.append(cv_file)

    # The archived posting, and any work sample you send to this company alone.
    (target / "posting").mkdir()
    paths.attachments(slug).mkdir()
    return written


def application_title(letter_data: dict, dossier: dict) -> tuple[str, str | None]:
    """(job title, where it came from). letter.yaml's job.title is the one that
    was sent; the dossier's role.title exists only for an application without a
    letter.yaml, which is why the dossier usually has none."""
    title = (letter_data.get("job") or {}).get("title")
    if title:
        return title, "letter.yaml job.title"
    title = (dossier.get("role") or {}).get("title")
    if title:
        return title, "dossier.yaml role.title"
    return "", None


def application_company(letter_data: dict, dossier: dict) -> tuple[str, str | None]:
    """(company, where it came from): the dossier's display name if set, else
    the legal entity the letter is addressed to."""
    name = (dossier.get("company") or {}).get("name")
    if name:
        return name, "dossier.yaml company.name"
    name = (letter_data.get("recipient") or {}).get("company")
    if name:
        return name, "letter.yaml recipient.company"
    return "", None


def application_date(slug: str, dossier: dict) -> str:
    """When this application happened, for sorting: sent, else started.

    `applied` if it was sent; else the first timeline entry, which `new`
    writes on the day it was created; else the slug's YYYY-MM prefix.
    """
    if dossier.get("applied"):
        return dossier["applied"]
    timeline = dossier.get("timeline") or []
    if timeline and timeline[0].get("date"):
        return timeline[0]["date"]
    prefix = re.match(r"\d{4}-\d{2}", slug)
    return prefix.group(0) if prefix else ""


def list_applications(
    match: list[str] | None = None, status: list[str] | None = None
) -> list[dict[str, Any]]:
    """Every application, newest first - optionally only those like a new one.

    Newest first because the documents get better with every iteration: of
    two similar applications, the recent one is the better starting point.
    `match` therefore filters but does not re-rank; the hit count is returned
    so the caller can weigh the two.
    """
    if not paths.APPLICATIONS.is_dir():
        return []

    words = [w.casefold() for w in match or []]
    rows = []
    for slug in check_mod._slugs():
        dossier = load_dossier(slug)
        letter_file = paths.letter_source(slug)
        letter_data = resolve.load_yaml(letter_file) if letter_file.is_file() else {}

        state = dossier.get("status") or "?"
        if status and state not in status:
            continue

        title, _ = application_title(letter_data, dossier)
        company, _ = application_company(letter_data, dossier)
        summary = " ".join((dossier.get("summary") or "").split())
        keywords = dossier.get("keywords") or []

        hits = None
        if words:
            # Not the job title: an unwritten letter still carries the
            # scaffold's "Rendering Engineer", and would match on it.
            haystack = " ".join([summary, *keywords]).casefold()
            hits = sum(1 for w in words if w in haystack)
            if not hits:
                continue

        rows.append(
            {
                "date": application_date(slug, dossier),
                "slug": slug,
                "status": state,
                "company": company,
                "title": title,
                "summary": summary,
                "keywords": keywords,
                "based_on": (dossier.get("approach") or {}).get("based_on"),
                "hits": hits,
            }
        )
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows
