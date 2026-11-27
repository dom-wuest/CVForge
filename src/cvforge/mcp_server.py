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
   dossier.yaml and posting/ of one application, and appends to
   guidance/learnings.md.

The tools split into read-only, drafting (refuse once an application is sent;
`remember` excepted - an outcome is learned after sending) and decisive
(`apply`, `mark_sent`, `log_event`, `update_event`, `set_track`) - the last
group is where Claude Desktop's per-tool approval is the user's confirmation.

Every tool that writes also rewrites <home>/dashboard.html (dashboard.py), so
the page the user reads never lags behind the dossiers. Its content stays on
this machine; no tool returns it.
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

import yaml
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, LiteralScalarString

from . import check as check_mod
from . import dashboard, guidance, letter, paths, posting, resolve, service
from . import notes as notes_mod

SLUG_RE = re.compile(r"^\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Set only by `mark_sent`, `log_event`, `update_event` and `set_track`, so that
# recording a submission or news is always its own call - one Claude Desktop
# asks you to approve.
DOSSIER_GUARDED = frozenset({"status", "applied", "timeline", "tracks"})

EventKind = Literal[
    "build",
    "submitted",
    "email",
    "call",
    "interview",
    "assessment",
    "trial-day",
    "feedback",
    "offer",
    "rejection",
    "other",
]
Channel = Literal["phone", "video", "email", "onsite", "portal", "post"]
Status = Literal["screening", "interview", "offer", "rejected", "withdrawn"]
TrackStatus = Literal[
    "proposed", "applied", "screening", "interview", "offer", "rejected", "withdrawn", "moved"
]
# The order a timeline entry's keys are written in, whoever wrote it.
EVENT_KEYS = (
    "date",
    "time",
    "kind",
    "channel",
    "with",
    "track",
    "planned",
    "approx",
    "event",
    "notes",
    "files",
)

INSTRUCTIONS = f"""\
CVForge builds job applications (cover letter + CV + certificates) for the user
from YAML. You read past applications, draft new ones and build them locally.

Guidance - read it first: at the start of every chat call get_guidance (unless
the new_application prompt already put it in the conversation). instructions.md
is the user's standing preferences and wins over your defaults, never over the
rules below. snippets.md is text the user has approved before: reuse it word
for word, adapting only the marked «…» parts, unless the user reworks it.
learnings.md is what earlier chats learned. Call remember, without asking, for
a lesson that will matter in later applications: the user corrects you or
states a preference, a portal's quirk, a fit fix that worked, or - after
log_event - an outcome together with the angle that was used. One or two
sentences, specific; nothing that only concerns one dossier.

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
4. Fit: build_draft reports the room left, how many lines the subject takes
   and, in the compact layout, how many the recipient takes. If the letter
   overflows or is tight, you may without asking, then tell the user what
   you changed: shorten a subject that wraps by setting `subject:` (drop the
   reference number first - the info block shows it anyway); in the compact
   layout remove the recipient's department and person; set meta.justify:
   true; set meta.layout: compact only if the application is submitted
   electronically. Never shorten or reword the body - propose cuts and let
   the user choose. The letterhead must fit its budget; trim sender_contacts
   if not.
5. apply builds the send-ready folder - only when the user asks for it. Tell
   the user the folder path; they review the real PDFs themselves.
6. mark_sent only when the user says it was submitted. log_event for later
   news (screening, interview, rejection, offer).

Recording what happens - the user reads it on a local dashboard that is
rebuilt after every change, so complete entries matter:
- One timeline entry per event (log_event) with kind, channel, time and
  `participants`: the names exactly as in the dossier's contacts. Add a new
  person with update_dossier first (contacts is a list - send all of them).
- What was said goes in that entry's `notes` (Markdown, see below) - not
  in the dossier notes and not in a contact's notes. A contact's notes hold
  facts about the person only: Du or Sie, background, how to reach them. The
  dossier notes hold what concerns the application as a whole.
- Anything ahead - an interview, a deadline, a promised call or answer - is
  its own entry with planned: true, and approx: true when the date is an
  estimate (use the earliest likely day). When it has happened, update_event
  that entry (planned false, the real date, the outcome, the notes) instead
  of adding a second one. Ask the user about a planned entry whose day has
  passed.
- A placement agency's client process, or another posting the company moved
  the user to, is a track (set_track) with its own status; its entries carry
  `track`. The application's status stays the relationship with the company
  applied to.

Where things are: the dossier is the record - status, dates, contacts, file
names. A brief.md is the frozen hand-over an application was first built
from; it is never updated, so its status line and file links go stale by
design. The job title lives in letter.yaml (job.title), not the dossier.

Rules: never change approved wording; never invent reference numbers, dates or
addresses - look a missing postal address up with web search (company imprint
or an official register) and record the source in the dossier notes. The
user's phone, address and signature never appear in your tool results - that
is by design, not a bug.

Notes - in timeline entries, contacts, tracks, the posting and the dossier -
are shown on the dashboard, which renders {notes_mod.SUBSET} Write multi-line notes as
they are; the server stores them as YAML block text.
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
                        if annotations is not READ:
                            dashboard.refresh()
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


def _misread(text: str) -> bool:
    """Whether PyYAML would read this string, unquoted, as something else.

    Everything but this server reads dossiers with PyYAML, which follows YAML
    1.1; ruamel writes YAML 1.2. In 1.1 an unquoted 2026-11-23 is a date, yes
    is a boolean and 14:00 is the base-60 integer 840 - which once put "840"
    on the dashboard as an interview time.
    """
    try:
        return yaml.safe_load(text) != text
    except yaml.YAMLError:
        return True


def _yaml_value(value: Any) -> Any:
    """A JSON value as ruamel should write it: prose as a block, and quoted
    wherever YAML 1.1 would read it as anything but this string."""
    if isinstance(value, dict):
        return {k: _yaml_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_yaml_value(v) for v in value]
    if isinstance(value, str):
        if "\n" in value:
            return LiteralScalarString(value)
        if _misread(value):
            return DoubleQuotedScalarString(value)
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


def _trailing(entry: Any) -> Any:
    """The comment token after an entry's last key - the blank line that
    separates the timeline from the next section, when it is the last entry."""
    if isinstance(entry, CommentedMap) and entry:
        return entry.ca.items.get(list(entry)[-1])
    return None


def _event(fields: dict) -> CommentedMap:
    """A timeline entry in EVENT_KEYS order, without the keys left empty."""
    kept = {k: fields[k] for k in EVENT_KEYS if fields.get(k) not in (None, "", [], False)}
    return CommentedMap(_yaml_value(kept))


def _insert_sorted(entries: list, entry: CommentedMap) -> None:
    """Into date order, after everything on the same day or earlier - so a
    late-logged event does not land behind a planned one."""
    position = len(entries)
    while position and str(entries[position - 1].get("date")) > entry["date"]:
        position -= 1
    if position == len(entries):
        _append(entries, dict(entry))
    else:
        entries.insert(position, entry)


def _remove(entries: list, index: int) -> None:
    trailing = _trailing(entries[index])
    del entries[index]
    if trailing and index == len(entries) and entries:
        last = entries[-1]
        if isinstance(last, CommentedMap) and last:
            last.ca.items[list(last)[-1]] = trailing


def _track_ids(data: dict) -> list[str]:
    return [t["id"] for t in data.get("tracks") or []]


def _check_event(data: dict, track: str | None, track_status: str | None, files) -> None:
    if track and track not in _track_ids(data):
        raise ToolError(f"no track {track!r} - add it with set_track first")
    if track_status and not track:
        raise ToolError("track_status needs the track it applies to")
    for rel in files or []:
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ToolError(f"files: {rel!r} must be relative to the application directory")


def _apply_status(data: dict, status: str | None, track: str | None, track_status: str | None):
    if status:
        data["status"] = status
    if track_status:
        for t in data["tracks"]:
            if t["id"] == track:
                t["status"] = track_status


def _timeline_warnings(slug: str, data: dict) -> list[str]:
    """`check`'s timeline warnings for this dossier: unknown names, overdue entries."""
    return check_mod._check_timeline(slug, json.loads(json.dumps(data, default=str)))


def _write_dossier(slug: str, change) -> dict:
    """Load dossier.yaml round-trip, apply `change`, validate, write. All or nothing."""
    source = paths.dossier(slug)
    y = _yaml()
    data = (y.load(source.read_text(encoding="utf-8")) if source.is_file() else None) or {}
    change(data)
    stream = io.StringIO()
    y.dump(data, stream)
    text = stream.getvalue()
    # Validated as `check` and the dashboard will read it - PyYAML, YAML 1.1 -
    # not as ruamel holds it in memory: the two disagree on unquoted 14:00.
    written = json.loads(json.dumps(yaml.safe_load(text), default=str))
    resolve.validate_against(written, paths.DOSSIER_SCHEMA, paths.display(source))
    source.write_text(text, encoding="utf-8")
    return written


# ─────────────────────────────────────────────────────────────────────────────
# Read-only
# ─────────────────────────────────────────────────────────────────────────────


@tool(READ)
def status() -> dict:
    """Where CVForge's data lives and whether this machine is ready: home folder,
    whether private.yaml and the signature exist (yes/no only), which guidance
    files exist, the repository version, the typst version, and the posting
    files waiting in the inbox."""
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
        "guidance": {
            "instructions": (paths.GUIDANCE / "instructions.md").is_file(),
            "snippets": (paths.GUIDANCE / "snippets.md").is_file(),
            "learnings_entries": guidance.entry_count(),
        },
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


def _guidance() -> dict:
    texts = guidance.read()
    out: dict[str, Any] = {name.removesuffix(".md"): text for name, text in texts.items()}
    missing = [name for name, text in texts.items() if text is None]
    if missing:
        out["unavailable"] = {
            name: f"no {paths.GUIDANCE.name}/{name} in the home yet" for name in missing
        }
    return out


@tool(READ)
def get_guidance() -> dict:
    """The user's guidance from <home>/guidance/: instructions (standing
    preferences - follow them), snippets (approved reusable paragraphs, DE and
    EN) and learnings (what earlier chats learned). Call at the start of every
    chat. A file that does not exist is null, with the reason under
    `unavailable`."""
    return _guidance()


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
    status, applied, timeline and tracks are set by mark_sent, log_event,
    update_event and set_track instead."""
    _slug(slug)
    guarded = DOSSIER_GUARDED & set(patch)
    if guarded:
        raise ToolError(
            f"{', '.join(sorted(guarded))}: use mark_sent, log_event, update_event or set_track"
        )
    return {"dossier": _write_dossier(slug, lambda data: _merge(data, patch))}


@tool(DRAFT)
def remember(text: str, slug: str | None = None, topic: str | None = None) -> dict:
    """Append a lesson to the user's learnings (guidance/learnings.md), dated,
    with the application it came from and an optional short topic ("tone",
    "portal", "layout", "outcome"). One or two sentences that will help a later
    application. Append-only: entries are never edited or removed by a tool -
    the user curates the file by hand."""
    if slug:
        _slug(slug)
    # Checked before writing, not only on the way out: a private value must
    # not reach a file that every later chat reads back.
    _guard(text)
    _guard(topic or "")
    return {"written": guidance.append_learning(text, slug, topic)}


@tool(DRAFT, with_log=True)
def build_draft(slug: str) -> dict:
    """Build letter and CV locally into out/ (never the send folder) and report:
    page counts against what is expected, the layout report in mm (room left or
    overflow for the letter body, the letterhead against its budget, the lines
    and height of the subject and - compact layout only - of the recipient, the
    CV's main column, sidebar and projects page) and the warnings for this
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
        entry = {"date": date, "kind": "submitted", "channel": method, "event": event}
        _insert_sorted(data.setdefault("timeline", []), _event(entry))

    return {"dossier": _write_dossier(slug, change)}


@tool(DECISIVE)
def log_event(
    slug: str,
    date: str,
    event: str,
    kind: EventKind | None = None,
    time: str | None = None,
    channel: Channel | None = None,
    participants: list[str] | None = None,
    notes: str | None = None,
    planned: bool = False,
    approx: bool = False,
    track: str | None = None,
    files: list[str] | None = None,
    status: Status | None = None,
    track_status: TrackStatus | None = None,
) -> dict:
    """Add a timeline entry - an invitation, a call, an interview, a rejection,
    an offer, or with planned=true something still ahead - and optionally set
    the application's new status (or, with track, that track's track_status).

    date: YYYY-MM-DD, the day it happened (planned: the day it will; approx=true
    when that is an estimate). time: "HH:MM", or "HH:MM-HH:MM" whenever the end
    or the length is known ("14:00, 90 minutes" is "14:00-15:30"). event: one line.
    participants: names exactly as in the dossier's contacts - the user is
    never listed. notes: what was said and agreed, in the Markdown the
    instructions list - "- " lists, **bold**, "> " to quote an email.
    files: paths relative to the application, e.g. recv/form_signed.pdf.
    Returns warnings, e.g. a participant who is not a contact yet."""
    _slug(slug)
    if not DAY_RE.match(date):
        raise ToolError("date must be YYYY-MM-DD")

    def change(data: dict) -> None:
        _check_event(data, track, track_status, files)
        entry = {
            "date": date,
            "time": time,
            "kind": kind,
            "channel": channel,
            "with": participants,
            "track": track,
            "planned": planned,
            "approx": approx,
            "event": event,
            "notes": notes,
            "files": files,
        }
        _insert_sorted(data.setdefault("timeline", []), _event(entry))
        _apply_status(data, status, track, track_status)

    written = _write_dossier(slug, change)
    return {"dossier": written, "warnings": _timeline_warnings(slug, written)}


@tool(DECISIVE)
def update_event(
    slug: str,
    date: str,
    match: str,
    new_date: str | None = None,
    event: str | None = None,
    kind: EventKind | None = None,
    time: str | None = None,
    channel: Channel | None = None,
    participants: list[str] | None = None,
    notes: str | None = None,
    planned: bool | None = None,
    approx: bool | None = None,
    track: str | None = None,
    files: list[str] | None = None,
    status: Status | None = None,
    track_status: TrackStatus | None = None,
) -> dict:
    """Change one timeline entry - above all a planned one that has now
    happened: planned=false, new_date the day it happened, event what
    happened, notes what was said. The entry is the one on `date` whose event
    contains `match` (case-insensitive); exactly one must. Parameters left out
    keep their value; given ones replace it (notes and participants too - read
    the entry first and pass the whole new text). "" clears time, notes or
    track. Optionally sets the status, like log_event."""
    _slug(slug)
    for day in (date, new_date):
        if day is not None and not DAY_RE.match(day):
            raise ToolError("dates must be YYYY-MM-DD")

    def change(data: dict) -> None:
        entries = data.get("timeline") or []
        found = [
            i
            for i, e in enumerate(entries)
            if str(e.get("date")) == date and match.casefold() in str(e.get("event")).casefold()
        ]
        if len(found) != 1:
            raise ToolError(
                f"{len(found)} entries on {date} contain {match!r} - it must be exactly one"
            )
        effective = track if track is not None else entries[found[0]].get("track")
        _check_event(data, effective or None, track_status, files)
        given = {
            "date": new_date,
            "time": time,
            "kind": kind,
            "channel": channel,
            "with": participants,
            "track": track,
            "planned": planned,
            "approx": approx,
            "event": event,
            "notes": notes,
            "files": files,
        }
        fields = {**dict(entries[found[0]]), **{k: v for k, v in given.items() if v is not None}}
        _remove(entries, found[0])
        _insert_sorted(entries, _event(fields))
        _apply_status(data, status, fields.get("track") or None, track_status)

    written = _write_dossier(slug, change)
    return {"dossier": written, "warnings": _timeline_warnings(slug, written)}


@tool(DECISIVE)
def set_track(
    slug: str,
    track: str,
    status: TrackStatus,
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> dict:
    """Add or update a track: one process inside this application with its own
    status - a client a placement agency proposed the user to, or another
    posting the company moved them to. track: a short lowercase id (mbda).
    On an existing track, parameters left out keep their value. Timeline
    entries point at it with log_event(track=...)."""
    _slug(slug)

    def change(data: dict) -> None:
        tracks = data.setdefault("tracks", [])
        given = {
            "company": company,
            "title": title,
            "location": location,
            "status": status,
            "notes": notes,
        }
        given = {k: v for k, v in given.items() if v is not None}
        for existing in tracks:
            if existing["id"] == track:
                _merge(existing, given)
                return
        tracks.append(CommentedMap(_yaml_value({"id": track, **given})))

    return {"dossier": _write_dossier(slug, change)}


# ─────────────────────────────────────────────────────────────────────────────
# Prompts - in Claude Desktop's "+" menu
# ─────────────────────────────────────────────────────────────────────────────


@server.prompt(
    title="New application",
    description="Start a new application with your guidance loaded and the inbox checked.",
)
def new_application(inbox_file: str | None = None) -> str:
    # Not a tool, so the tool() wrapper does not run: the privacy filter is
    # applied here by hand.
    with _lock:
        texts = guidance.read()
    posting_hint = (
        f"The posting is `{inbox_file}` in the inbox." if inbox_file else "Check the inbox."
    )
    parts = [
        "Let's write a new application. Follow the CVForge workflow: status, read_inbox, "
        f"list_applications, the closest earlier applications, the base CV. {posting_hint} "
        "My guidance is below - it is already loaded, no need to call get_guidance.",
    ]
    for name, text in texts.items():
        parts.append(f"## {name}\n\n{text}" if text else f"## {name}\n\n(not written yet)")
    try:
        return _guard("\n\n".join(parts))
    except ToolError as exc:
        return str(exc)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
