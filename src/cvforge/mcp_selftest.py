"""End-to-end test of the MCP server over real stdio.

    uv run --extra mcp python -m cvforge.mcp_selftest

Starts `cvforge-mcp` the way Claude Desktop does, against a throwaway home in a
temporary directory with FAKE private data, and calls every tool. Asserts the
guard rails (slugs, rollback, the sent lock) and, above all, that no fake
private value appears in any response - including one planted in a letter.

The real home and the real private.yaml are never touched. Part of the
verification recipe in CLAUDE.md: run it after any change to mcp_server.py,
service.py, or the leak scanner.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path

import yaml
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from . import paths

FAKE_PRIVATE = """\
contacts:
  phone:
    value: "+49 999 7654321"
    url: "tel:+499997654321"
address:
  street: "Scratchweg 7"
  postal_code: "12345"
  city: "Teststadt"
signature: "private/signature.png"
documents:
  - id: fake
    file: "private/documents/fake.pdf"
    label: "Testzeugnis"
"""
FAKE_VALUES = ("7654321", "+49 999", "Scratchweg", "4999765")
POSTING = "# Test Engineer at Scratch Corp\n\n" + "We build test rigs in C++ and Python. " * 20
SLUG, LONG = "2026-11-selftest", "2026-11-selftest-long"


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + kind + data + crc

    rows = b"".join(b"\x00" + b"\x00\x00\x00\xff" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def _make_home(home: Path) -> None:
    (home / "private" / "documents").mkdir(parents=True)
    (home / "inbox").mkdir()
    (home / "private" / "signature.png").write_bytes(_png(80, 20))
    (home / "private" / "documents" / "fake.pdf").write_bytes(b"%PDF-1.4\n% fake\n")
    (home / "private.yaml").write_text(FAKE_PRIVATE, encoding="utf-8")
    (home / "inbox" / "posting.md").write_text(POSTING, encoding="utf-8")


async def _run(home: Path) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    seen: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"  -- {detail[:200]}" if not ok else ""))

    params = StdioServerParameters(
        command=shutil.which("uv") or "uv",
        args=["run", "--directory", str(paths.ROOT), "--extra", "mcp", "cvforge-mcp"],
        env={**os.environ, "CVFORGE_HOME": str(home)},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        async def call(name: str, **args) -> tuple[bool, str]:
            res = await session.call_tool(name, args)
            text = "".join(getattr(c, "text", "") for c in res.content)
            seen.append(text)
            return res.is_error, text

        app = home / "applications" / SLUG

        err, text = await call("status")
        st = json.loads(text) if not err else {}
        check("status", st.get("private_yaml") and st.get("signature"), text)
        err, text = await call("read_inbox", file="posting.md")
        check("read_inbox", not err and "Scratch Corp" in text, text)
        err, text = await call("read_inbox", file="../private.yaml")
        check("read_inbox refuses a path", err, text)
        err, text = await call("create_application", slug="../evil", lang="en", tailored_cv=True)
        check("traversal slug refused", err, text)

        err, text = await call("create_application", slug=SLUG, lang="en", tailored_cv=True)
        check("create_application", not err, text)
        err, text = await call("import_posting", slug=SLUG, inbox_file="posting.md")
        check("import_posting", not err and (app / "posting" / "posting.md").is_file(), text)

        edits = [
            {"old": 'company: "ACME GmbH"', "new": 'company: "Scratch Corp"'},
            {"old": "attachments: []", "new": "attachments: [fake]"},
        ]
        err, text = await call("edit_file", slug=SLUG, file="letter", edits=edits)
        check("edit_file", not err, text)
        before = (app / "letter.yaml").read_text("utf-8")
        err, text = await call(
            "edit_file", slug=SLUG, file="letter", edits=[{"old": "lang: en", "new": "lang: fr"}]
        )
        same = (app / "letter.yaml").read_text("utf-8") == before
        check("invalid edit rolled back", err and same, text)
        err, text = await call(
            "edit_file", slug=SLUG, file="letter", edits=[{"old": "TODO", "new": "x"}]
        )
        check("non-unique edit refused", err, text)

        patch = {"summary": "Test rigs.", "keywords": ["testing"], "posting": {"notes": "a\nb"}}
        err, text = await call("update_dossier", slug=SLUG, patch=patch)
        check("update_dossier", not err, text)
        err, text = await call("update_dossier", slug=SLUG, patch={"status": "applied"})
        check("update_dossier refuses status", err, text)
        err, text = await call("update_dossier", slug=SLUG, patch={"role": {"work_model": "moon"}})
        check("update_dossier validates", err, text)

        err, text = await call("list_applications", match=["testing"])
        check("list_applications", not err and SLUG in text, text)
        err, text = await call("get_application", slug=SLUG)
        got = json.loads(text) if not err else {}
        check("get_application", got.get("letter_yaml"), text)
        # A requested part that does not exist is null with a reason, never
        # silently absent - a missing key reads as a bug to whoever asked.
        explicit = "brief_md" in got and got["brief_md"] is None
        explained = "brief.md" in got.get("unavailable", {})
        check("missing part is explicit", explicit and explained, text)
        check("title names its source", (got.get("title") or {}).get("from"), text)

        err, text = await call("build_draft", slug=SLUG)
        draft = json.loads(text) if not err else {}
        check("build_draft", draft.get("letter_pages") == 1, text)
        check("draft leaves send/ alone", not (app / "send").exists())
        layout = draft.get("letter_layout") or {}
        check("subject lines reported", (layout.get("subject") or {}).get("lines") == 1, text)
        check("no recipient lines in din", "recipient" not in layout, text)

        # A subject that wraps, and the compact layout: both now measured.
        long_subject = "Application for " + "a very long job title indeed " * 4
        edits = [
            {"old": "subject: null", "new": f'subject: "{long_subject.strip()}"'},
            {"old": "layout: din", "new": "layout: compact"},
        ]
        err, text = await call("edit_file", slug=SLUG, file="letter", edits=edits)
        check("edit to a wrapping subject", not err, text)
        err, text = await call("build_draft", slug=SLUG)
        layout = (json.loads(text).get("letter_layout") or {}) if not err else {}
        check("wrapped subject counted", (layout.get("subject") or {}).get("lines") == 2, text)
        check("compact recipient lines", (layout.get("recipient") or {}).get("lines", 0) >= 3, text)

        # Guidance: missing at first, then a learning appended and read back.
        err, text = await call("get_guidance")
        g = json.loads(text) if not err else {}
        missing = g.get("learnings") is None and "learnings.md" in g.get("unavailable", {})
        check("get_guidance without files", not err and missing, text)
        err, text = await call("remember", text="Portals take one PDF.", slug=SLUG, topic="portal")
        check("remember", not err and "Portals take one PDF." in text, text)
        err, text = await call("remember", text="Call +49 999 7654321 first.")
        learnings = home / "guidance" / "learnings.md"
        stored = learnings.read_text("utf-8") if learnings.is_file() else ""
        check("private value never remembered", err and "7654321" not in stored, text)
        err, text = await call("get_guidance")
        check("learning read back", not err and "Portals take one PDF." in text, text)
        err, text = await call("status")
        st = json.loads(text) if not err else {}
        check("status counts learnings", st.get("guidance", {}).get("learnings_entries") == 1, text)
        prompts = await session.list_prompts()
        check("new_application prompt", any(p.name == "new_application" for p in prompts.prompts))
        res = await session.get_prompt("new_application", {"inbox_file": "posting.md"})
        prompt_text = "".join(getattr(m.content, "text", "") for m in res.messages)
        seen.append(prompt_text)
        check("prompt carries learnings", "Portals take one PDF." in prompt_text, prompt_text)

        err, text = await call("apply", slug=SLUG)
        check("apply", not err and len(json.loads(text)["files"]) == 3, text)
        err, text = await call("mark_sent", slug=SLUG, date="2026-11-02", method="portal")
        check("mark_sent", not err, text)
        err, text = await call("apply", slug=SLUG)
        check("apply refused once sent", err, text)
        err, text = await call(
            "edit_file", slug=SLUG, file="letter", edits=[{"old": "Scratch Corp", "new": "X"}]
        )
        check("edit refused once sent", err, text)

        # People, a track, and a planned entry that later happens.
        people = [{"name": "Ada Probe", "role": "HR"}, {"name": "Kurt Test", "org": "Kunde"}]
        err, text = await call("update_dossier", slug=SLUG, patch={"contacts": people})
        check("contacts added once sent", not err, text)
        err, text = await call("update_dossier", slug=SLUG, patch={"tracks": []})
        check("update_dossier refuses tracks", err, text)
        err, text = await call("log_event", slug=SLUG, date="2026-11-04", event="X", track="kunde")
        check("unknown track refused", err, text)
        err, text = await call(
            "set_track", slug=SLUG, track="kunde", status="proposed", company="Kunde GmbH"
        )
        check("set_track", not err, text)
        err, text = await call(
            "log_event",
            slug=SLUG,
            date="2099-01-05",
            time="10:00-11:00",
            kind="interview",
            channel="video",
            participants=["Kurt Test"],
            track="kunde",
            planned=True,
            event="Interview at the client",
            track_status="interview",
        )
        got = json.loads(text) if not err else {}
        tracks = (got.get("dossier") or {}).get("tracks") or [{}]
        check("planned event logged", tracks[0].get("status") == "interview", text)
        err, text = await call(
            "log_event",
            slug=SLUG,
            date="2026-11-03",
            time="14:00",
            participants=["Nobody"],
            event="A call",
        )
        got = json.loads(text) if not err else {}
        warned = any("'Nobody' is not in contacts" in w for w in got.get("warnings", []))
        check("unknown participant warned", warned, text)
        # Unquoted, 14:00 is the integer 840 to YAML 1.1 - what check and the
        # dashboard read with. It once reached the dashboard that way.
        timeline = yaml.safe_load((app / "dossier.yaml").read_text("utf-8"))["timeline"]
        times = [e.get("time") for e in timeline if e.get("event") == "A call"]
        check("time survives YAML 1.1", times == ["14:00"], repr(times))
        err, text = await call("update_event", slug=SLUG, date="2099-01-05", match="nothing")
        check("update_event needs exactly one match", err, text)
        err, text = await call(
            "update_event",
            slug=SLUG,
            date="2099-01-05",
            match="client",
            new_date="2026-11-05",
            planned=False,
            event="Interview at the client, went well",
            notes="- asked about tests\n- next round in two weeks",
        )
        got = json.loads(text) if not err else {}
        timeline = (got.get("dossier") or {}).get("timeline") or []
        done = [e for e in timeline if e.get("date") == "2026-11-05"]
        completed = bool(done) and "planned" not in done[0] and "next round" in done[0]["notes"]
        check("planned event completed", completed, text)
        dates = [e["date"] for e in timeline]
        check("timeline in date order", dates == sorted(dates), ", ".join(dates))
        page = home / "dashboard.html"
        html = page.read_text("utf-8") if page.is_file() else ""
        seen.append(html)  # the leak test below covers the page too
        check("dashboard rewritten", "went well" in html and "Kurt Test" in html)

        err, text = await call(
            "log_event", slug=SLUG, date="2026-11-10", event="No", status="rejected"
        )
        check("log_event", not err, text)

        letter = app / "letter.yaml"
        letter.write_text(
            letter.read_text("utf-8").replace("Scratch Corp", "Call +49 999 7654321"), "utf-8"
        )
        err, text = await call("get_application", slug=SLUG, parts=["letter"])
        check("planted private value withheld", err and "contacts.phone" in text, text)

        await call("create_application", slug=LONG, lang="de", tailored_cv=False)
        filler = "Ein absichtlich langer Absatz, der den Brief sprengt. " * 45
        await call(
            "edit_file",
            slug=LONG,
            file="letter",
            edits=[{"old": "TODO: der Beleg.", "new": filler.strip()}],
        )
        err, text = await call("build_draft", slug=LONG)
        body = (json.loads(text).get("letter_layout") or {}).get("body") if not err else {}
        check("overflow reported in mm", (body or {}).get("overflow_mm", 0) > 0, text)

    leaked = [v for v in FAKE_VALUES if any(v in t for t in seen)]
    check("no private value in any response", not leaked, ", ".join(leaked))
    return results


def main() -> int:
    home = Path(tempfile.mkdtemp(prefix="cvforge-selftest-"))
    try:
        _make_home(home)
        results = asyncio.run(_run(home))
    finally:
        shutil.rmtree(home, ignore_errors=True)
        # The build artifacts of exactly the two scratch slugs, nothing else.
        for slug in (SLUG, LONG):
            for path in (
                paths.letter_resolved(slug),
                paths.cv_resolved_for(slug),
                paths.letter_pdf(slug),
                paths.draft_cv_pdf(slug),
            ):
                path.unlink(missing_ok=True)
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
