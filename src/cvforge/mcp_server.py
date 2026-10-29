"""CVForge as a local MCP server for Claude Desktop - `cvforge-mcp`, over stdio.

Claude Desktop starts this process and talks to it on stdin/stdout. It opens no
port and makes no request of its own; everything happens in the home and the
repository on this machine.

What it must never do is put a private value into a tool result. Claude runs
remotely, so a result is conversation content the moment it is returned. Three
independent layers keep private.yaml out of it:

1. By construction. No tool reads private.yaml except through resolve/letter,
   and no tool returns the contents of build/, send/ or the private folder -
   builds report numbers, file names and warnings.
2. The output filter. Every result and every error message is scanned for the
   same needles `check-clean` uses (check._private_needles). A hit withholds
   the whole result and names only the trail, never the value.
3. No dangerous verbs. No delete, no `apply --force`, no export, no path a
   caller can choose: slugs are validated, writes go to letter.yaml, cv.yaml,
   dossier.yaml and posting/ of one application.

The tools split into read-only, drafting (refuse once an application is sent)
and decisive (`apply`, `mark_sent`, `log_event`) - the last group is where
Claude Desktop's per-tool approval is the user's confirmation.
"""

from __future__ import annotations

import contextlib
import datetime
import difflib
import functools
import io
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, LiteralScalarString

from . import check as check_mod
from . import letter, paths, posting, resolve, service

SLUG_RE = re.compile(r"^\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Set only by `mark_sent` and `log_event`, so that recording a submission is
# always its own call - one Claude Desktop asks you to approve.
DOSSIER_GUARDED = frozenset({"status", "applied", "timeline"})

INSTRUCTIONS = """\
CVForge builds job applications (cover letter + CV + certificates) for the user
from YAML. You read past applications, draft new ones and build them locally.

Workflow for a new posting:
1. status, then read_inbox for the posting the user saved to the inbox.
2. list_applications, then get_application for the 2-3 most similar RECENT ones
   (newer applications are better: the documents improve with every iteration).
   get_base_cv for the language. Propose: slug (YYYY-MM-company-role), angle,
   CV changes, letter text, gaps. Discuss with the user until they say final.
3. Only after the user says the texts are final: create_application (based_on
   the closest earlier one if it fits), import_posting, edit_file for letter
   and CV, update_dossier (summary, keywords, company, role, approach,
   submission, a looked-up address with its source), then build_draft.
4. Fit: if build_draft reports overflow, you may set meta.justify: true, and
   meta.layout: compact only if the application is submitted electronically.
   Never shorten or reword text on your own - propose cuts and let the user
   choose. The letterhead must fit its budget; trim sender_contacts if not.
5. apply builds the send-ready folder - only when the user asks for it. Tell
   the user the folder path; they review the real PDFs themselves.
6. mark_sent only when the user says it was submitted. log_event for later
   news (screening, interview, rejection, offer).

Where things are: the dossier is the record - status, dates, contacts, file
names. A brief.md is the frozen hand-over an application was first built
from; it is never updated, so its status line and file links go stale by
design. The job title lives in letter.yaml (job.title), not the dossier.

Rules: never change approved wording; never invent reference numbers, dates or
addresses - look a missing postal address up with web search (company imprint
or an official register) and record the source in the dossier notes. The
user's phone, address and signature never appear in your tool results - that
is by design, not a bug.
"""

server = MCPServer(name="cvforge", instructions=INSTRUCTIONS)
_lock = threading.Lock()

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
DRAFT = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
DECISIVE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)


class Edit(BaseModel):
    old: str
    new: str


# ─────────────────────────────────────────────────────────────────────────────
# The privacy layer
# ─────────────────────────────────────────────────────────────────────────────


def _needles() -> list[tuple[str, str]]:
    # Recomputed per call: private.yaml may change while Desktop keeps the
    # server running, and a stale list is exactly how a new value would leak.
    return check_mod._private_needles() if paths.PRIVATE.is_file() else []


def _guard(text: str) -> str:
    for trail, needle in _needles():
        if needle in text:
            raise ToolError(
                f"Withheld: this response would have contained the private value "
                f"`{trail}` from private.yaml. Nothing was returned. If it comes from "
                f"a file you wrote (letter, CV, dossier), remove the value there."
            )
    return text


def tool(annotations: ToolAnnotations, *, with_log: bool = False):
    """Register a tool, with the privacy filter and stdout capture around it."""

    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            buffer = io.StringIO()
            with _lock:
                try:
                    if paths.HOME_PROBLEM and fn.__name__ != "status":
                        raise resolve.ResolveError(paths.HOME_PROBLEM)
                    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                        result = fn(*args, **kwargs)
                except ToolError as exc:
                    raise ToolError(_guard(str(exc))) from None
                except resolve.ResolveError as exc:
                    raise ToolError(_guard(str(exc))) from None
                except Exception as exc:  # a bug - still never leak through it
                    message = f"internal error: {type(exc).__name__}: {exc}"
                    raise ToolError(_guard(message)) from None
            if with_log and isinstance(result, dict):
                result["log"] = [
                    line.strip()
                    for line in buffer.getvalue().splitlines()
                    if re.match(r"\s*(note|warning|error)\b", line)
                ]
            return _guard(json.dumps(result, ensure_ascii=False, indent=1, default=str))

        return server.tool(annotations=annotations, structured_output=False)(wrapper)

    return decorate


def _slug(slug: str, *, exists: bool = True) -> Path:
    if not SLUG_RE.match(slug):
        raise ToolError(f"invalid slug {slug!r}: expected YYYY-MM-company-role, lowercase")
    directory = paths.application(slug)
    if directory.resolve().parent != paths.APPLICATIONS.resolve():
        raise ToolError(f"invalid slug {slug!r}")
    if exists and not directory.is_dir():
        raise ToolError(f"no application {slug!r} - list_applications shows the existing ones")
    return directory


def _inbox_file(name: str) -> Path:
    if Path(name).name != name or name.startswith("."):
        raise ToolError(f"{name!r}: give a file name from the inbox, not a path")
    path = paths.inbox() / name
    if not path.is_file():
        raise ToolError(f"{name!r} is not in the inbox ({paths.display(paths.inbox())})")
    if path.suffix.lower() not in posting.POSTING_SUFFIXES:
        raise ToolError(f"{name!r}: only PDF, Markdown or text postings")
    return path


def _git(*args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(paths.ROOT), *args], capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip() if result.returncode == 0 else None


# ─────────────────────────────────────────────────────────────────────────────
# Dossier writes - comments preserved
# ─────────────────────────────────────────────────────────────────────────────


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 88
    y.indent(mapping=2, sequence=4, offset=2)
    # `null`, as the scaffold writes it, rather than an empty value.
    y.representer.add_representer(
        type(None), lambda r, _: r.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    return y


def _yaml_value(value: Any) -> Any:
    """A JSON value as ruamel should write it: dates quoted, prose as a block."""
    if isinstance(value, dict):
        return {k: _yaml_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_yaml_value(v) for v in value]
    if isinstance(value, str):
        if DAY_RE.match(value):
            # Unquoted, YAML reads a date object, and the schema rejects it.
            return DoubleQuotedScalarString(value)
        if "\n" in value:
            return LiteralScalarString(value)
    return value


def _merge(target: dict, patch: dict) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
            continue
        target[key] = _yaml_value(value)
        if isinstance(target[key], LiteralScalarString) and hasattr(target, "ca"):
            # The scaffold's hint comment sat after `null`; after a block it
            # would dangle below the text as a stray line. The blank lines
            # that followed it are kept - they separate the sections.
            token = (target.ca.items.get(key) or [None, None, None])[2]
            blank = token.value.split("\n", 1)[1] if token and "\n" in token.value else ""
            if blank:
                token.value = blank
            else:
                target.ca.items.pop(key, None)


def _append(entries: list, entry: dict) -> None:
    """Append to a YAML list, keeping the blank line that followed it last."""
    entry = CommentedMap(_yaml_value(entry))
    previous = entries[-1] if entries else None
    if isinstance(previous, CommentedMap) and previous:
        last_key = list(previous)[-1]
        trailing = previous.ca.items.pop(last_key, None)
        if trailing:
            entry.ca.items[list(entry)[-1]] = trailing
    entries.append(entry)


def _write_dossier(slug: str, change) -> dict:
    """Load dossier.yaml round-trip, apply `change`, validate, write. All or nothing."""
    source = paths.dossier(slug)
    y = _yaml()
    data = (y.load(source.read_text(encoding="utf-8")) if source.is_file() else None) or {}
    change(data)
    resolve.validate_against(
        json.loads(json.dumps(data, default=str)), paths.DOSSIER_SCHEMA, paths.display(source)
    )
    stream = io.StringIO()
    y.dump(data, stream)
    source.write_text(stream.getvalue(), encoding="utf-8")
    return json.loads(json.dumps(data, default=str))


# ─────────────────────────────────────────────────────────────────────────────
# Read-only
# ─────────────────────────────────────────────────────────────────────────────


@tool(READ)
def status() -> dict:
    """Where CVForge's data lives and whether this machine is ready: home folder,
    whether private.yaml and the signature exist (yes/no only), the repository
    version, the typst version, and the posting files waiting in the inbox."""
    private = paths.PRIVATE.is_file()
    signature = None
    if private:
        declared = resolve.load_yaml(paths.PRIVATE).get("signature")
        signature = bool(declared) and paths.private_path(declared).is_file()
    inbox = paths.inbox()
    behind = _git("rev-list", "--count", "HEAD..@{u}")
    return {
        "home": str(paths.HOME or paths.ROOT),
        "home_problem": paths.HOME_PROBLEM,
        "private_yaml": private,
        "signature": signature,
        "applications": len(check_mod._slugs()),
        "inbox": [p.name for p in posting.archived(inbox)],
        "inbox_folder": str(inbox),
        "repo": {
            "head": _git("rev-parse", "--short", "HEAD"),
            "uncommitted_files": len((_git("status", "--porcelain") or "").splitlines()),
            "commits_behind_upstream_as_last_fetched": int(behind) if behind else None,
        },
        "typst": service.typst_version(),
    }


@tool(READ)
def list_applications(
    status: list[str] | None = None, match: list[str] | None = None
) -> list[dict]:
    """Every application, newest first: date, status, company, title, summary,
    keywords, based_on. `status` filters (draft, applied, screening, interview,
    offer, rejected, withdrawn); `match` keeps those whose summary or keywords
    contain any of the words. Judge similarity from the summaries yourself.
    The title is letter.yaml's job.title (dossier role.title only when there is
    no letter); the company is the dossier's company.name, else the letter's
    recipient."""
    return service.list_applications(match, status)


@tool(READ)
def get_application(
    slug: str,
    parts: list[Literal["letter", "dossier", "cv_diff", "posting", "brief", "files"]] | None = None,
) -> dict:
    """One application. Default parts: letter (letter.yaml), dossier
    (dossier.yaml), cv_diff (how its cv.yaml differs from the base CV), brief,
    files (names in send/, posting/, attachments/). Ask for "posting" to get the
    archived posting's text. Every requested part comes back: a part that does
    not exist is null, with the reason under `unavailable`.

    `title` and `company` are resolved the way list_applications shows them,
    with their source - the title is letter.yaml's job.title, so the dossier
    normally has no role.title. brief.md, where present, is the frozen hand-over
    the application was first built from: trust the dossier for status, dates
    and file names, not the brief."""
    directory = _slug(slug)
    wanted = list(dict.fromkeys(parts or ["letter", "dossier", "cv_diff", "brief", "files"]))
    out: dict[str, Any] = {"slug": slug}
    unavailable: dict[str, str] = {}

    letter_file = paths.letter_source(slug)
    letter_data = resolve.load_yaml(letter_file) if letter_file.is_file() else {}
    dossier = service.load_dossier(slug)
    lang = (letter_data.get("meta") or {}).get("lang")
    title, title_from = service.application_title(letter_data, dossier)
    company, company_from = service.application_company(letter_data, dossier)
    out["title"] = {"value": title or None, "from": title_from}
    out["company"] = {"value": company or None, "from": company_from}
    out["sent"] = service.sent_on(slug)

    def text_of(path: Path, reason: str) -> str | None:
        if path.is_file():
            return path.read_text(encoding="utf-8")
        unavailable[path.name] = reason
        return None

    for part in wanted:
        if part == "letter":
            out["letter_yaml"] = text_of(letter_file, "no letter.yaml - built before CVForge")
        elif part == "dossier":
            out["dossier_yaml"] = text_of(paths.dossier(slug), "no dossier.yaml")
        elif part == "brief":
            out["brief_md"] = text_of(
                directory / "brief.md", "no brief.md - not built from a brief"
            )
        elif part == "cv_diff":
            cv_file = paths.cv_override(slug)
            out["cv_diff"] = None
            if not cv_file.is_file():
                unavailable["cv_diff"] = "no tailored cv.yaml - the base CV was used"
            elif not lang:
                unavailable["cv_diff"] = "no letter.yaml, so the base CV's language is unknown"
            else:
                base = paths.source(lang)
                out["cv_diff"] = "".join(
                    difflib.unified_diff(
                        base.read_text(encoding="utf-8").splitlines(keepends=True),
                        cv_file.read_text(encoding="utf-8").splitlines(keepends=True),
                        fromfile=paths.display(base),
                        tofile=f"{slug}/cv.yaml",
                        n=1,
                    )
                )
        elif part == "posting":
            archived = posting.archived(directory / "posting")
            out["posting"] = {p.name: posting.extract_text(p) for p in archived} or None
            if not archived:
                unavailable["posting"] = "nothing archived in posting/"
        elif part == "files":
            out["files"] = {
                sub: sorted(p.name for p in (directory / sub).iterdir() if p.is_file())
                if (directory / sub).is_dir()
                else []
                for sub in ("send", "posting", "attachments")
            }
    if unavailable:
        out["unavailable"] = unavailable
    return out


@tool(READ)
def get_base_cv(lang: Literal["en", "de"]) -> dict:
    """The base CV, data/cv-<lang>.yaml - public data with placeholders for the
    private contacts (it also feeds the website). A tailored CV starts from it."""
    source = paths.source(lang)
    return {"file": paths.display(source), "yaml": source.read_text(encoding="utf-8")}


@tool(READ)
def get_reference(
    kind: Literal[
        "cv_schema", "letter_schema", "dossier_schema", "letter_scaffold", "authoring_rules"
    ],
) -> dict:
    """Reference material: the JSON schemas, the letter.yaml scaffold with its
    comments, or the authoring rules (how fields map, YAML gotchas)."""
    files = {
        "cv_schema": paths.CV_SCHEMA,
        "letter_schema": paths.LETTER_SCHEMA,
        "dossier_schema": paths.DOSSIER_SCHEMA,
        "letter_scaffold": paths.APPLICATION_TEMPLATE / "letter.yaml",
        "authoring_rules": paths.ROOT / ".claude/skills/new-application/field-mapping.md",
    }
    return {"kind": kind, "text": files[kind].read_text(encoding="utf-8")}


@tool(READ)
def list_documents() -> list[dict]:
    """The certificates that can be attached, by id: their labels per language
    and whether each file is present. Attach them by id in letter.yaml."""
    out = []
    for did, entry in sorted(check_mod._document_pool().items()):
        files = entry.get("file")
        per_lang = files if isinstance(files, dict) else {"any": files}
        out.append(
            {
                "id": did,
                "label": entry.get("label"),
                "file_present": {
                    lang: bool(rel) and paths.private_path(rel).is_file()
                    for lang, rel in per_lang.items()
                },
            }
        )
    return out


@tool(READ)
def read_inbox(file: str) -> dict:
    """The text of a posting waiting in the inbox (see status for the names)."""
    path = _inbox_file(file)
    return {"file": path.name, "text": posting.extract_text(path)}


# ─────────────────────────────────────────────────────────────────────────────
# Drafting
# ─────────────────────────────────────────────────────────────────────────────


@tool(DRAFT)
def create_application(
    slug: str, lang: Literal["en", "de"], tailored_cv: bool, based_on: str | None = None
) -> dict:
    """Scaffold a new application: letter.yaml, dossier.yaml, posting/,
    attachments/ and, with tailored_cv, a cv.yaml copy to tailor. With
    based_on (an earlier slug in the same language), letter.yaml and its
    tailored CV start as copies of that application and the dossier records it.
    Slug: YYYY-MM-company-role, lowercase, e.g. 2026-11-acme-rendering."""
    _slug(slug, exists=False)
    if based_on:
        _slug(based_on)
    written = service.new_application(slug, lang, tailored_cv=tailored_cv, from_slug=based_on)
    return {
        "slug": slug,
        "written": [p.name for p in written],
        "next": "edit_file the letter (and cv), update_dossier, then build_draft",
    }


@tool(DRAFT)
def import_posting(slug: str, inbox_file: str) -> dict:
    """Move a posting from the inbox into the application's posting/ folder,
    record it in the dossier (posting.archive, posting.fetched = today) and
    return its text."""
    _slug(slug)
    source = _inbox_file(inbox_file)
    target = paths.application(slug) / "posting" / source.name
    if target.exists():
        raise ToolError(f"posting/{source.name} already exists in {slug}")
    target.parent.mkdir(exist_ok=True)
    shutil.move(source, target)

    today = datetime.date.today().isoformat()

    def change(data: dict) -> None:
        _merge(data, {"posting": {"archive": f"posting/{source.name}", "fetched": today}})

    _write_dossier(slug, change)
    return {"archived": f"posting/{source.name}", "text": posting.extract_text(target)}


@tool(DRAFT)
def edit_file(slug: str, file: Literal["letter", "cv"], edits: list[Edit]) -> dict:
    """Change letter.yaml or the tailored cv.yaml by exact string replacement.
    Each `old` must occur exactly once. All edits apply together, and the result
    is validated by actually resolving the letter and CV; on any error nothing
    is written and the errors come back. Read the file with get_application
    first. Refused once the application is sent."""
    _slug(slug)
    service.refuse_if_sent(slug, f"editing its {file}")
    target = paths.letter_source(slug) if file == "letter" else paths.cv_override(slug)
    if not target.is_file():
        hint = " - it uses the base CV, so there is nothing to tailor" if file == "cv" else ""
        raise ToolError(f"{slug} has no {target.name}{hint}")

    before = target.read_text(encoding="utf-8")
    text = before
    for i, edit in enumerate(edits):
        count = text.count(edit.old)
        if count != 1:
            raise ToolError(
                f"edits[{i}]: `old` occurs {count} times in {target.name} - it must be unique"
            )
        text = text.replace(edit.old, edit.new)

    target.write_text(text, encoding="utf-8")
    try:
        letter.resolve_letter(slug)  # validates letter.yaml and the CV it uses
        if file == "cv":
            lang = resolve.load_yaml(paths.letter_source(slug))["meta"]["lang"]
            resolve.validate(resolve.load_yaml(target), lang, target)
    except Exception:
        target.write_text(before, encoding="utf-8")
        raise
    return {"file": target.name, "edits": len(edits), "valid": True}


@tool(DRAFT)
def update_dossier(slug: str, patch: dict) -> dict:
    """Merge `patch` into dossier.yaml (nested objects merge, lists and values
    replace) and validate it. For summary, keywords, company, role, posting,
    approach, submission, contacts, notes - see get_reference('dossier_schema').
    status, applied and timeline are set by mark_sent and log_event instead."""
    _slug(slug)
    guarded = DOSSIER_GUARDED & set(patch)
    if guarded:
        raise ToolError(f"{', '.join(sorted(guarded))}: use mark_sent or log_event")
    return {"dossier": _write_dossier(slug, lambda data: _merge(data, patch))}


@tool(DRAFT, with_log=True)
def build_draft(slug: str) -> dict:
    """Build letter and CV locally into out/ (never the send folder) and report:
    page counts against what is expected, the layout report in mm (room left or
    overflow for the letter body, the letterhead against its budget, the CV's
    main column, sidebar and projects page) and the warnings for this
    application. No document content is returned."""
    _slug(slug)
    result = service.build_draft(slug)
    return {
        "letter_pages": result.letter_pages,
        "cv_pages": result.cv_pages,
        "cv_pages_expected": result.expected_cv_pages,
        "cv_source": paths.display(result.cv_source),
        "letter_layout": result.letter_layout,
        "cv_layout": result.cv_layout,
        "subject_max_chars": check_mod.SUBJECT_MAX,
        "warnings": result.warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Decisive - the user approves each call in Claude Desktop
# ─────────────────────────────────────────────────────────────────────────────


@tool(DECISIVE, with_log=True)
def apply(slug: str) -> dict:
    """Build the send-ready folder <home>/applications/<slug>/send/: letter,
    CV and every attachment, numbered. Only when the user asks for it. Refused
    once the application is marked sent - the folder is then the record of what
    the employer received. Returns the folder path for the user to review."""
    _slug(slug)
    result = service.apply_application(slug, force=False)
    return {
        "folder": str(result.folder),
        "files": result.files,
        "letter_pages": result.letter_pages,
        "cv_pages": result.cv_pages,
        "cv_pages_expected": result.expected_cv_pages,
        "summary": result.summary_line(),
    }


@tool(DECISIVE)
def mark_sent(
    slug: str,
    date: str,
    method: Literal["portal", "email", "post"] | None = None,
    note: str | None = None,
) -> dict:
    """Record that the user submitted the application on `date` (YYYY-MM-DD):
    sets applied, status: applied and a timeline entry. Only when the user says
    it was submitted. From then on the send folder is locked."""
    _slug(slug)
    if not DAY_RE.match(date):
        raise ToolError("date must be YYYY-MM-DD")
    if service.sent_on(slug):
        raise ToolError(f"{slug} is already recorded as sent ({service.sent_on(slug)})")

    def change(data: dict) -> None:
        patch: dict[str, Any] = {"applied": date, "status": "applied"}
        if method:
            patch["submission"] = {"method": method}
        _merge(data, patch)
        event = "Submitted" + (f" via {method}" if method else "") + (f" - {note}" if note else "")
        _append(data.setdefault("timeline", []), {"date": date, "event": event})

    return {"dossier": _write_dossier(slug, change)}


@tool(DECISIVE)
def log_event(
    slug: str,
    date: str,
    event: str,
    status: Literal["screening", "interview", "offer", "rejected", "withdrawn"] | None = None,
) -> dict:
    """Add a timeline entry - an interview invitation, a rejection, an offer -
    and optionally set the new status. `date` is YYYY-MM-DD."""
    _slug(slug)
    if not DAY_RE.match(date):
        raise ToolError("date must be YYYY-MM-DD")

    def change(data: dict) -> None:
        _append(data.setdefault("timeline", []), {"date": date, "event": event})
        if status:
            data["status"] = status

    return {"dossier": _write_dossier(slug, change)}


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
