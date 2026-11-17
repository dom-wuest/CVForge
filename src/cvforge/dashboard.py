"""`cvforge dashboard`: every application on one local page, for reading.

The dossiers are the data. This module derives everything the page shows -
what is coming up, what needs attention, the pipeline, the activity strip, each
person's history - and embeds it as JSON in one self-contained HTML file. The
page only navigates and draws, the way the Typst templates only draw what
resolve composed.

It is written into the home, beside applications/, so its links are relative
and work on every machine the home syncs to, and so the recruiters' details and
interview notes it carries stay where the dossiers already are. Nothing here
reads private.yaml. The MCP server rewrites the page after every change;
`cvforge dashboard` does it on demand.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from . import check as check_mod
from . import paths, resolve, service

ACTIVE = ("applied", "screening", "interview", "offer")
CONVERSATION = ("screening", "interview", "offer")
COLUMNS = ("applied", "screening", "interview", "offer")
# Shown only with "All": what is not, or no longer, in play.
OTHER_COLUMNS = ("draft", "rejected", "withdrawn")

# Days without news after which an application is waiting too long.
STALE_DAYS = 10
# How far ahead "Next up" looks.
AHEAD_DAYS = 21
# The activity strip covers this many days before and after today.
STRIP_BACK, STRIP_AHEAD = 42, 18

KIND_LABELS = {
    "build": "Build",
    "submitted": "Submitted",
    "email": "Email",
    "call": "Call",
    "interview": "Interview",
    "assessment": "Assessment",
    "trial-day": "Trial day",
    "feedback": "Feedback",
    "offer": "Offer",
    "rejection": "Rejection",
    "other": "Update",
}

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _date(value: Any) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def day_label(day: dt.date) -> str:
    return f"{DAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"


def short_label(day: dt.date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]}"


def _initials(name: str) -> str:
    words = [w for w in name.replace("(", " ").replace(")", " ").split() if not w.endswith(".")]
    return "".join(w[0] for w in (words[:1] + words[-1:] if len(words) > 1 else words)).upper()


def _href(path: Path) -> str:
    """A link from the page to `path`: relative, so it works on every machine."""
    try:
        return quote(path.relative_to(paths.DASHBOARD.parent).as_posix())
    except ValueError:
        return path.as_uri()


def _blocks(text: str) -> list[dict[str, Any]]:
    """Notes as paragraphs and lists: "- " starts an item, an indented line
    continues it, a blank line ends a paragraph."""
    out: list[dict[str, Any]] = []
    para: list[str] = []
    items: list[str] | None = None

    def flush() -> None:
        if para:
            out.append({"text": " ".join(para)})
            para.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            items = None
        elif line.startswith(("- ", "* ")):
            flush()
            if items is None:
                items = []
                out.append({"items": items})
            items.append(line[2:].strip())
        elif items is not None and raw[:1] in (" ", "\t"):
            items[-1] += " " + line
        else:
            items = None
            para.append(line)
    flush()
    return out


# ─────────────────────────────────────────────────────────────────────────────
# One application
# ─────────────────────────────────────────────────────────────────────────────


def _events(slug: str, dossier: dict, track_names: dict[str, str], today: dt.date) -> list[dict]:
    """The timeline, newest first - so what is planned comes on top."""
    out = []
    for index, entry in enumerate(dossier.get("timeline") or []):
        day = _date(entry.get("date"))
        if day is None:
            continue
        planned = bool(entry.get("planned"))
        approx = bool(entry.get("approx"))
        kind = entry.get("kind") or "other"
        label = KIND_LABELS.get(kind, "Update") + (" expected" if planned and approx else "")
        track = entry.get("track") or ""
        out.append(
            {
                "id": f"e{index}",
                "index": index,
                "date": day.isoformat(),
                "day": day_label(day),
                "short": short_label(day),
                "time": entry.get("time") or ("approx." if approx else ""),
                "kind": kind,
                "kind_label": label,
                "channel": entry.get("channel") or "",
                "people": [{"name": n, "initials": _initials(n)} for n in entry.get("with") or []],
                "track": track,
                "track_label": track_names.get(track, track),
                "planned": planned,
                "approx": approx,
                "overdue": planned and day < today,
                "event": " ".join(str(entry.get("event", "")).split()),
                "notes": _blocks(entry.get("notes") or ""),
                "files": [
                    {"name": Path(rel).name, "href": _href(paths.application(slug) / rel)}
                    for rel in entry.get("files") or []
                ],
            }
        )
    out.sort(key=lambda e: (e["date"], e["index"]), reverse=True)
    return out


def _next_step(status: str, events: list[dict], days_waiting: int | None) -> dict | None:
    planned = sorted((e for e in events if e["planned"]), key=lambda e: (e["date"], e["index"]))

    def prefix(e: dict) -> str:
        return f"{e['track_label']}: " if e["track_label"] else ""

    overdue = [e for e in planned if e["overdue"]]
    if overdue:
        e = overdue[0]
        state = "still open" if e["approx"] else "not logged"
        return {"text": f"{prefix(e)}{e['kind_label']} {e['short']} {state}", "tone": "warn"}
    if planned:
        e = planned[0]
        when = e["day"] + (f", {e['time']}" if e["time"] and not e["approx"] else "")
        return {"text": f"{prefix(e)}{e['kind_label']} {when}", "tone": "soon"}
    if status == "applied" and days_waiting is not None:
        tone = "warn" if days_waiting >= STALE_DAYS else "plain"
        return {"text": f"Waiting · {days_waiting} days", "tone": tone}
    return None


def _contacts(dossier: dict, events: list[dict], company: str) -> list[dict]:
    out = []
    for contact in dossier.get("contacts") or []:
        name = contact["name"]
        mine = [e for e in events if any(p["name"] == name for p in e["people"])]
        past = [e for e in mine if not e["planned"]]
        coming = sorted((e for e in mine if e["planned"]), key=lambda e: e["date"])
        activity = [f"{len(past)} event{'s' if len(past) != 1 else ''}"]
        if past:
            activity.append(f"last {past[0]['short']}")
        if coming:
            activity.append(f"next {coming[0]['short']}")
        out.append(
            {
                "name": name,
                "initials": _initials(name),
                "role": contact.get("role") or "",
                "org": contact.get("org") or company,
                "email": contact.get("email") or "",
                "phone": contact.get("phone") or "",
                "notes": _blocks(contact.get("notes") or ""),
                "activity": " · ".join(activity),
                "last": past[0]["date"] if past else "",
                "next": coming[0]["date"] if coming else "",
            }
        )
    return out


SOURCES = ("letter.yaml", "cv.yaml", "dossier.yaml", "brief.md")
FOLDERS = (
    ("Sent", "send"),
    ("Received", "recv"),
    ("Posting", "posting"),
    ("Attachments", "attachments"),
)


def _files(slug: str) -> list[dict]:
    directory = paths.application(slug)

    def entries(files: list[Path]) -> list[dict]:
        return [{"name": p.name, "href": _href(p)} for p in files]

    groups = []
    for label, sub in FOLDERS:
        folder = directory / sub
        files = sorted(p for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []
        if files:
            groups.append({"label": f"{label} · {sub}/", "files": entries(files)})
    sources = [directory / name for name in SOURCES if (directory / name).is_file()]
    other = sorted(p for p in directory.iterdir() if p.is_file() and p.name not in SOURCES)
    if other:
        groups.append({"label": "Other", "files": entries(other)})
    groups.append({"label": "Sources", "files": entries(sources)})
    return groups


def _track_label(track: dict, company: str) -> str:
    """What tells a track apart: the client an agency proposed you to, or -
    when the company moved you to another posting - that posting's title."""
    other = track.get("company")
    if other and other != company:
        return other
    return track.get("title") or other or track["id"]


def _application(slug: str, today: dt.date) -> dict[str, Any]:
    dossier = service.load_dossier(slug)
    letter_file = paths.letter_source(slug)
    letter_data = resolve.load_yaml(letter_file) if letter_file.is_file() else {}
    title, _ = service.application_title(letter_data, dossier)
    company, _ = service.application_company(letter_data, dossier)
    status = dossier.get("status") or "draft"
    tracks = dossier.get("tracks") or []
    track_names = {t["id"]: _track_label(t, company) for t in tracks}

    events = _events(slug, dossier, track_names, today)
    past = [e for e in events if not e["planned"]]
    last = _date(past[0]["date"]) if past else None
    days_since = (today - last).days if last else None
    applied = _date(dossier.get("applied"))

    role = dossier.get("role") or {}
    posting = dossier.get("posting") or {}
    approach = dossier.get("approach") or {}
    submission = dossier.get("submission") or {}
    archive = posting.get("archive")
    fetched, deadline = _date(posting.get("fetched")), _date(posting.get("deadline"))

    facts = [role.get("location"), role.get("work_model"), role.get("employment")]
    if applied:
        via = f" via {submission['method']}" if submission.get("method") else ""
        facts.append(f"applied {day_label(applied)}{via}")
        facts.append(f"{(today - applied).days} days in process")
    meta = [role.get("location"), role.get("work_model")]
    meta.append(f"applied {short_label(applied)}" if applied else status)

    return {
        "slug": slug,
        "company": company or slug,
        "title": title,
        "status": status,
        "active": status in ACTIVE,
        "lang": (letter_data.get("meta") or {}).get("lang") or "",
        "tailored_cv": paths.cv_override(slug).is_file(),
        "date": service.application_date(slug, dossier),
        "facts": [f for f in facts if f],
        "meta": " · ".join(m for m in meta if m),
        "summary": " ".join((dossier.get("summary") or "").split()),
        "keywords": dossier.get("keywords") or [],
        "about": " ".join(((dossier.get("company") or {}).get("about") or "").split()),
        "posting": {
            "url": posting.get("url") or "",
            "archive": _href(paths.application(slug) / archive) if archive else "",
            "fetched": short_label(fetched) if fetched else "",
            "deadline": day_label(deadline) if deadline else "",
            "notes": _blocks(posting.get("notes") or ""),
        },
        "approach": {
            "based_on": approach.get("based_on") or "",
            "angle": " ".join((approach.get("angle") or "").split()),
            "cv": approach.get("cv") or [],
            "gaps": approach.get("gaps") or [],
        },
        "submission": {
            "url": submission.get("url") or "",
            "questions": submission.get("questions") or [],
        },
        "tracks": [
            {
                "id": t["id"],
                "label": track_names[t["id"]],
                "company": t.get("company") or "",
                "title": t.get("title") or "",
                "location": t.get("location") or "",
                "status": t["status"],
                "notes": _blocks(t.get("notes") or ""),
            }
            for t in tracks
        ],
        "events": events,
        "contacts": _contacts(dossier, events, company),
        "notes": _blocks(dossier.get("notes") or ""),
        "files": _files(slug),
        "folder": _href(paths.application(slug)) + "/",
        "last": last.isoformat() if last else "",
        "days_since": days_since,
        "next": _next_step(status, events, days_since),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Across applications
# ─────────────────────────────────────────────────────────────────────────────


def _strip(apps: list[dict], today: dt.date) -> dict[str, Any]:
    """One row per active application, a dot per event, on a fixed window."""
    start = today - dt.timedelta(days=STRIP_BACK)
    span = STRIP_BACK + STRIP_AHEAD

    def pct(day: str | dt.date) -> float:
        offset = ((_date(day) if isinstance(day, str) else day) - start).days
        return round(max(0, min(span, offset)) / span * 100, 2)

    ticks = []
    for offset in range(span + 1):
        day = start + dt.timedelta(days=offset)
        if day.day in (1, 15) and abs(pct(day) - pct(today)) > 4:
            ticks.append({"left": pct(day), "label": short_label(day)})

    rows = []
    seen_kinds: set[str] = set()
    for app in apps:
        # CVForge's own "Created"/"Built" entries are not contact with anyone,
        # and they sit on the same day as the submission.
        events = [e for e in reversed(app["events"]) if e["kind"] != "build"]
        if not app["active"] or not events:
            continue
        positions = [pct(e["date"]) for e in events]
        seen_kinds.update(e["kind"] for e in events)
        # Oldest first: the page spreads crowded badges left to right in this order.
        dots = [
            {
                "left": pct(e["date"]),
                "kind": e["kind"],
                "look": "overdue" if e["overdue"] else "planned" if e["planned"] else "done",
                "title": f"{e['day']} · {e['kind_label']} · {e['event']}",
            }
            for e in events
        ]
        tracks = len(app["tracks"])
        rows.append(
            {
                "slug": app["slug"],
                "name": app["company"],
                "sub": app["status"] + (f" · {tracks} tracks" if tracks else ""),
                "from": min(positions),
                "width": round(max(positions) - min(positions), 2),
                "dots": dots,
            }
        )
    kinds = [{"kind": k, "label": label} for k, label in KIND_LABELS.items() if k in seen_kinds]
    return {"today": pct(today), "ticks": ticks, "rows": rows, "kinds": kinds}


def _next_up(apps: list[dict], today: dt.date) -> list[dict]:
    horizon = (today + dt.timedelta(days=AHEAD_DAYS)).isoformat()
    out = []
    for app in apps:
        for e in app["events"]:
            if e["planned"] and not e["overdue"] and e["date"] <= horizon:
                out.append({**e, "slug": app["slug"], "company": app["company"]})
    out.sort(key=lambda e: (e["date"], e["approx"], e["time"]))
    return out


def _attention(apps: list[dict], today: dt.date) -> list[dict]:
    out = []
    for app in apps:
        for e in sorted((e for e in app["events"] if e["overdue"]), key=lambda e: e["date"]):
            where = f"{app['company']} › {e['track_label']}" if e["track_label"] else app["company"]
            names = ", ".join(p["name"] for p in e["people"])
            if e["approx"]:
                text = f"{e['kind_label']} around {e['day']}: {e['event']}. Did it arrive?"
            else:
                time = f" {e['time']}" if e["time"] else ""
                who = f" with {names}" if names else ""
                text = (
                    f"{e['kind_label']} on {e['day']}{time}{who} has no entry since. How did it go?"
                )
            out.append({"slug": app["slug"], "company": where, "text": text, "tone": "warn"})
    for app in apps:
        days = app["days_since"]
        if app["status"] == "applied" and days is not None and days >= STALE_DAYS:
            out.append(
                {
                    "slug": app["slug"],
                    "company": app["company"],
                    "text": f"Applied, no news for {days} days.",
                    "tone": "plain",
                }
            )
        if app["status"] == "draft" and app["posting"]["deadline"]:
            out.append(
                {
                    "slug": app["slug"],
                    "company": app["company"],
                    "text": f"Draft - the posting closes {app['posting']['deadline']}.",
                    "tone": "warn",
                }
            )
    return out


def _people(apps: list[dict]) -> list[dict]:
    """Everyone, grouped by who they work for, most recently in touch first."""
    groups: dict[str, list[dict]] = {}
    for app in apps:
        for c in app["contacts"]:
            groups.setdefault(c["org"], []).append(
                {**c, "slug": app["slug"], "application": f"{app['company']} · {app['title']}"}
            )
    out = []
    for org, people in groups.items():
        people.sort(key=lambda c: c["next"] or c["last"], reverse=True)
        out.append({"org": org, "people": people, "latest": people[0]["next"] or people[0]["last"]})
    out.sort(key=lambda g: g["latest"], reverse=True)
    return out


def collect(now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now()
    today = now.date()
    apps = [_application(slug, today) for slug in check_mod._slugs()]
    apps.sort(key=lambda a: a["last"] or a["date"], reverse=True)

    def count(statuses: tuple[str, ...]) -> int:
        return sum(1 for a in apps if a["status"] in statuses)

    horizon = (today + dt.timedelta(days=14)).isoformat()
    dates = sum(
        1
        for a in apps
        for e in a["events"]
        if e["planned"] and not e["overdue"] and e["date"] <= horizon
    )
    return {
        "generated": f"{day_label(today)} {today.year}, {now:%H:%M}",
        "today": today.isoformat(),
        "count": len(apps),
        "kpis": [
            {"value": count(ACTIVE), "label": "active"},
            {"value": count(CONVERSATION), "label": "in conversation"},
            {"value": count(("applied",)), "label": "waiting for a first reply"},
            {"value": dates, "label": "dates in the next 14 days"},
            {"value": count(("offer",)), "label": "offers"},
        ],
        "next_up": _next_up(apps, today),
        "attention": _attention(apps, today),
        "columns": list(COLUMNS),
        "other_columns": list(OTHER_COLUMNS),
        "strip": _strip(apps, today),
        "people": _people(apps),
        "applications": apps,
    }


def write(now: dt.datetime | None = None) -> Path:
    """Render the page into the home. Returns its path."""
    payload = json.dumps(collect(now), ensure_ascii=False, separators=(",", ":"))
    # Inside <script>, "</script>" in a recruiter's note would end the block.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = paths.DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    html = template.replace("/*CVFORGE_DATA*/null", payload, 1)
    # The logo goes in as it is in assets/logo - embedded, so the page stays a
    # single file that works offline from any synced copy of the home.
    favicon = (paths.LOGO / "cvforge-favicon.svg").read_text(encoding="utf-8").strip()
    html = html.replace("/*CVFORGE_FAVICON*/", "data:image/svg+xml," + quote(favicon, safe=""), 1)
    mark = (paths.LOGO / "cvforge-mark.svg").read_text(encoding="utf-8").strip()
    html = html.replace("<!--CVFORGE_MARK-->", mark, 1)
    paths.DASHBOARD.write_text(html, encoding="utf-8")
    return paths.DASHBOARD


def refresh() -> None:
    """Rewrite the page after a change. A failure is a warning: the change it
    follows has already been written and must not be reported as failed."""
    try:
        write()
    except Exception as exc:  # anything at all - see the docstring
        print(f"  warning: dashboard not updated: {type(exc).__name__}: {exc}")
