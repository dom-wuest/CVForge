# Working with Claude

[← README](../README.md) · [Getting started](getting-started.md) · [CV](cv.md) · [Private data](private-data.md) · [Cover letters](cover-letters.md) · [Applications](applications.md) · [Tracking](tracking.md) · [Website](website.md) · **Claude** · [Commands](commands.md)

---

CVForge has two integrations with Claude, for two ways of working:

| | Claude Desktop | Claude Code |
|---|---|---|
| How | A local MCP server, `cvforge-mcp` | The `/new-application` skill in this repository |
| Workflow | Write the letter and build the application in the same chat | Hand over a brief from a separate letter-writing chat |
| Can | Read past applications, draft, build, record what happens after | Scaffold, fill in, tailor the CV, `apply`, report |

Both work through the same commands you would run yourself, and neither
removes a decision from you: wording, sending and recording a submission stay
yours.

- [Claude Desktop](#claude-desktop)
  - [Setup, once per machine](#setup-once-per-machine)
  - [What leaves your machine](#what-leaves-your-machine)
  - [A new application](#a-new-application)
  - [Fitting the letter on one page](#fitting-the-letter-on-one-page)
  - [Guidance and memory](#guidance-and-memory)
  - [The tools](#the-tools)
- [Claude Code](#claude-code)

## Claude Desktop

A local MCP server lets Claude Desktop read your past applications, draft a
new one with you and build it - in the same chat where you write the letter.
No brief to hand over, no second session.

### Setup, once per machine

```bash
uv sync --extra mcp
uv run cvforge mcp-config      # prints the entry for this machine
```

Paste the printed entry into Claude Desktop's config (Settings → Developer →
Edit Config) and restart Claude Desktop. In its tool settings, set the
read-only tools to *Always allow* and keep `apply`, `mark_sent`, `log_event`,
`update_event` and `set_track` on *Ask* - those prompts are your
confirmations. A second machine runs the same two commands after `git pull`
and `cvforge home set`.

### What leaves your machine

The server is local: no port, no network access of its own. But Claude runs at
Anthropic, so whatever a tool *returns* goes there - as it already does when
you paste a posting into a chat.

| Goes to Claude | Never does |
|---|---|
| Postings, letter.yaml, cv.yaml (placeholders), dossiers, your guidance files, page counts, layout numbers, warnings | Phone, address, private e-mail - anything in `private.yaml` - the signature, the certificates, the built PDFs |

Every result is scanned for every value in `private.yaml` before it is
returned; a hit is withheld, naming only where the value came from. No page
images are sent - Claude fits the layout from numbers ("3.5 mm left",
"overflows 12 mm"), and you look at the PDFs.

The server cannot delete anything, cannot `--force`, and cannot export to the
website.

### A new application

🟦 you start · 🟩 you do · 🟧 you confirm

1. 🟩 Print the posting to PDF into `<home>/inbox/` (a chat attachment cannot
   reach a local server).
2. 🟦 In Claude Desktop: *"New posting in the inbox."* Claude reads it, finds
   the most similar recent applications and proposes the angle, CV changes and
   the letter.
3. 🟩 Work on the text together.
4. 🟧 *"Final."* Claude creates the application, fills letter, CV and dossier,
   builds a draft and fits it to one page with layout settings. Cuts it only
   proposes - 🟧 you choose.
5. 🟧 Approve `apply`. 🟩 Open `<home>/applications/<slug>/send/` and check
   the real PDFs.
6. 🟩 Submit. 🟦 *"Submitted today."* → 🟧 approve `mark_sent`; `send/` is
   locked from then on.
7. 🟦 Later: *"Interview invitation from X for the 14th"*, *"Rejection from
   Y"* → 🟧 approve `log_event`. The interview itself goes in as a planned
   entry; afterwards, *"The interview went well, notes: …"* → 🟧 approve
   `update_event`, which turns that entry into the record with your notes.
   An agency's client process (*"they proposed me to Z"*) → 🟧 `set_track`.

Any time, without prompts: *"Which applications are open?"*, *"What did I lead
with for rendering jobs?"* Claude rewrites the [dashboard](tracking.md#the-dashboard)
after every change; reload the tab.

You can also start from the **New application** prompt in Desktop's "+" menu.

### Fitting the letter on one page

To fit the letter on one page, Claude may, without asking:

- shorten a subject line that wraps, dropping the reference number first,
  since it is printed beside the address anyway;
- in the compact layout, remove the department and contact person from the
  recipient;
- switch `justify` or the `compact` [layout](cover-letters.md#layout).

It tells you what it changed. It never shortens the letter text itself.

### Guidance and memory

A local chat in Claude Desktop has no Project library, so the server provides
one from `<home>/guidance/`, synced with the rest of the home:

| File | Who writes it | What it is |
|---|---|---|
| `instructions.md` | you | Standing preferences: tone, content, process. Claude follows them. |
| `snippets.md` | you | Approved paragraphs from earlier letters, DE and EN. Claude reuses them word for word and adapts only the `«…»` parts. |
| `learnings.md` | Claude | One dated line per lesson, added without asking. Condense or delete entries whenever you like. |

Claude reads all three at the start of each chat; the **New application**
prompt loads them for you. `cvforge home` shows whether the folder exists.

### The tools

| | Tools | Approval |
|---|---|---|
| Read | `status`, `list_applications`, `get_application`, `get_base_cv`, `get_reference`, `list_documents`, `read_inbox`, `get_guidance` | none needed |
| Draft | `create_application`, `import_posting`, `edit_file`, `update_dossier`, `build_draft`, `remember` | writes drafts only - never `send/` |
| Decide | `apply`, `mark_sent`, `log_event`, `update_event`, `set_track` | Desktop asks every time |

`edit_file` refuses once an application is sent, like `apply`.
`update_dossier` cannot change the status, the applied date, the timeline or
tracks - recording a submission or news is always its own, approved call.

## Claude Code

`.claude/skills/new-application/` turns a markdown brief into a built
application. Write the letter in a chat of your choice, have it produce a brief
in [the expected format](../.claude/skills/new-application/brief-format.md),
then in Claude Code:

```
/new-application brief.md posting.pdf
```

(or attach both). The skill scaffolds the application, fills `letter.yaml` and
`dossier.yaml`, applies the brief's *confirmed* CV changes to a tailored
`cv.yaml`, runs `apply`, looks at the PDFs and reports page counts and
anything that needs you. It changes layout settings to fit a page but never
the wording. A brief without a postal address gets one looked up - from the
company's imprint or an official register - and the report flags it for you
to confirm.

The repository also ships a hook, `.claude/hooks/protect_private.py`, that
stops Claude Code from overwriting, moving or deleting `private.yaml`, the
private folder or the home's applications - reading them is still allowed.
