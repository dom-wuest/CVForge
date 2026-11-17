# CLAUDE.md — working on CVForge

This file is for anyone changing the code or the templates. Editing the CV
content or writing an application needs only the [README](README.md).

CVForge turns one YAML source into an A4 CV (Typst), the public data for a
website, and complete job applications — cover letter, CV and attachments in
a send-ready folder. German and English. Private data (phone, address,
signature, certificates) is kept out of every tracked file by construction.

---

## Contents

- [Guardrails](#guardrails)
- [Architecture](#architecture)
- [Project layout](#project-layout)
- [Conventions](#conventions)
- [The private-data guarantee](#the-private-data-guarantee)
- [The home](#the-home)
- [The resolve step](#the-resolve-step)
- [Cover letters](#cover-letters)
- [Styling the CV](#styling-the-cv)
- [Publishing to the website](#publishing-to-the-website)
- [The MCP server](#the-mcp-server)
- [The dashboard](#the-dashboard)
- [Troubleshooting](#troubleshooting)
- [Verification recipe](#verification-recipe)

---

## Guardrails

**Never overwrite, move or delete `private.yaml` or anything under the
private folder** — `data/private.yaml` and `assets/private/` in the repository,
or `<home>/private.yaml` and `<home>/private/` once a [home](#the-home) is set
(`uv run cvforge home` says which). The same goes for the home's
`applications/` as a whole. None of it is in git — a deleted signature scan or
certificate is gone, and OneDrive syncs a deletion as faithfully as a file. This has happened once, from a
test that ran `cp data/private.example.yaml data/private.yaml` and a cleanup
that ran `rm -rf data/private.yaml assets/private`. The user's real
`private.yaml` was only recovered because VS Code happened to have a local
history snapshot; the signature scan had to be re-scanned.

For tests:

- Prefer a **scratch home**: `CVFORGE_HOME=<a new empty dir>` for the shell
  running the test. Nothing in the real home or the repository is touched,
  and a fake `private.yaml` there is yours to create and delete.
- Never create a real `private.yaml` if it exists. Read it if you need to know
  what is in it; do not print its values.
- Use a scratch application slug (`cvforge new scratch-…`) and delete only
  that directory afterwards.
- Never write to the real private folder. If a test needs a document, point a
  scratch letter's one-off `{file, label}` entry at a file under the scratch
  application's own `attachments/`.
- Cleanup commands must name the files they created, not patterns. Never
  `rm -rf` a directory you did not create in the same session.

`build/` and `out/` are generated and safe to delete. An application's `send/`
folder is emptied by `apply` by design.

---

## Architecture

```
data/cv-en.yaml ─┐
data/cv-de.yaml ─┼─→ build/cv-<lang>.json ──┬─→ out/cv-<lang>.pdf            (profile=full)
private.yaml    ─┘   (the resolved artifact) └─→ the website's data/ + static/  (profile=public)
   (in the home)

applications/<slug>/letter.yaml ─┐
applications/<slug>/cv.yaml      │  (tailored CV if present, else data/cv-<lang>.yaml)
  or data/cv-<lang>.yaml (sender)┼─→ build/letter-<slug>.json ─→ out/letters/<slug>.pdf
private.yaml (address, sig)     ─┘                              ─→ applications/<slug>/send/  (apply)
                                     build/cv-app-<slug>.json  ─┘  (tailored CV only)
```

`private.yaml` and `applications/` are in the [home](#the-home) - a folder
outside the repository - when one is set, and in the repository (gitignored)
when not. `build/` and `out/` are always local.

**Renderers read only the resolved JSON.** Neither Typst template reads YAML,
and neither knows `private.yaml` exists. `resolve.py` (CV) and `letter.py`
(letter) are the only modules that read YAML or know about private data.
Everything a renderer would otherwise compute — formatted dates, the education
meta line, the subject line, the Anlagen list, section labels — is derived in
Python and placed into the artifact. Typst does no string logic. This is what
lets a third target (plain text, JSON-LD, an ATS variant) be added without
touching the data.

**A letter is a sibling target, not a CV section.** It has its own YAML, its
own schema, its own resolve module and its own Typst entry point. It calls
`resolve.resolve(lang, "full")` for the sender identity rather than restating
it, so the letterhead cannot disagree with the CV.

**Two languages are two files.** `data/cv-en.yaml` and `data/cv-de.yaml` have
identical structure and nothing forces them to agree. Renderer strings — section
headings, *Present* / *heute*, month names — are not in the data; they live in
`src/cvforge/i18n.py` and are emitted into the artifact under `labels`, so no
renderer carries its own copy. To add a language: a block there, a
`data/cv-<lang>.yaml`, done.

---

## Project layout

```
data/                The CV content and private.example.yaml. Source of truth.
applications/_template/   The scaffold `cvforge new` copies. The only tracked
                     part of applications/; without a home, the applications
                     themselves live beside it, gitignored.
cvforge.local.toml   GITIGNORED. This machine's home (`cvforge home set`).
.claude/             Claude Code: the /new-application skill, the private-file
                     hook and its settings. Tracked; holds no private data.
schema/              JSON Schema for cv, letter and dossier; wired into VS Code.
src/cvforge/
  paths.py             Every repo path, resolved once - and the home. Add path helpers here.
  home.py              `cvforge home`: show or set the home; the schema mirror.
  resolve.py           CV: load -> validate -> merge private -> derive -> write.
  letter.py            Letter: the same shape, plus attachments.
  check.py             `check` (content warnings) and `check-clean` (leak scan).
  dates.py             "YYYY"/"YYYY-MM" for the CV; "YYYY-MM-DD" for the letter.
  i18n.py              LABELS (CV, shipped to the website) and LETTER_LABELS.
  service.py           What the commands do, returning results: typst, apply, new,
                       draft builds, the layout report, list. CLI and MCP both call it.
  cli.py               argparse and printing; thin over service.py.
  posting.py           Text of an archived posting (pypdf).
  guidance.py          <home>/guidance/: read the three files, append a learning.
  dashboard.py         Every dossier derived into JSON, embedded in <home>/dashboard.html.
  mcp_server.py        The local MCP server for Claude Desktop (`cvforge-mcp`).
  mcp_selftest.py      Its end-to-end test against a throwaway home.
templates/pdf/       The CV renderer.
  theme.typ            Every design token. No magic numbers anywhere else.
  template.typ         Page geometry and set/show rules.
  icons.typ            Font Awesome behind one function; FALLBACK flag.
  components/          header, contact row, chips, bars, timeline, sidebar, and
                       marker.typ (invisible layout metadata for the report).
  sections/            One module per CV section.
  main.typ             Assembly only.
templates/dashboard/ dashboard.html: the page dashboard.py fills. Vanilla JS, no CDN.
templates/letter/    The letter renderer. Imports ../pdf/ for theme, icons and
                     the contact row, so the two cannot drift apart on look.
assets/
  fonts/               Committed, SIL OFL. Inter, JetBrains Mono, Font Awesome 7.
  logo/                build.py and the SVGs it writes: README header (light/dark,
                       animated), mark, favicon. Edit build.py, never the SVGs.
  projects/            Screenshots for the projects page.
  private/             GITIGNORED. Without a home: signature.png and documents/.
build/  out/         Generated. Both gitignored.
```

The home (a OneDrive folder on the user's machines):

```
private.yaml             contacts, address, signature, documents manifest
private/                 signature.png, documents/ - paths in private.yaml are relative to the home
applications/<slug>/
  letter.yaml              the letter
  cv.yaml                  optional tailored CV (`new --cv`)
  dossier.yaml             the posting, recruiter contacts, status
  brief.md                 the brief /new-application was run from
  posting/                 the archived posting
  attachments/             one-off files for this job
  recv/                    documents received from them (forms, questionnaires), linked from events
  send/                    what `apply` built - emptied and refilled on every run
dashboard.html           every application on one page - rewritten, never edited
schema/                  a mirror of schema/, kept current by `new`, `check`, `home set`
guidance/                instructions.md, snippets.md (the user's), learnings.md (Claude appends)
```

There is no `templates/web/`. Web presentation lives in the Portfolio repo.

---

## Conventions

**Python.** Ruff, line length 100, rules `E F I UP B SIM`. Run
`uv run ruff check src/ && uv run ruff format src/` before finishing.
`from __future__ import annotations` everywhere. No test suite — the
[verification recipe](#verification-recipe) is the test.

**Errors.** `resolve.ResolveError` is the only exception `cli.main` catches;
it prints without a traceback. Raise it for anything user-fixable. Anything
else is a bug and should traceback.

**Output.** Commands print `  note: …` for informational lines and
`  wrote <repo-relative path>  (…)` for artifacts. `paths.display()` makes a
path repo-relative where possible and absolute otherwise (`export` writes
outside the repo). `service.compile_typst` appends the page count as `(N pages)`.

**Typst.** Every `.typ` file opens with a `// ─── name.typ ───` banner
explaining *why* it exists. Formatted by typstyle at 100 columns (Tinymist does
it on save). `theme.typ` imports nothing and is the single source of every
constant — if a component needs a number, it becomes a key there. JSON keys are
`snake_case` because Typst treats `a-b` and `a_b` as different identifiers.
`show` is a Typst keyword and cannot be a bare dictionary key.

**Data, not presentation.** Compose display strings in Python, in the resolve
step, and keep every composed value overridable from the YAML. Never sort
downstream; file order is display order.

**Additive private data.** `private.yaml` has no schema. `merge_private`
reads only `private.get("contacts")`, `private_letter` reads `address`,
`signature` and `documents`. New top-level keys are additive and break
nothing, but every new leaf string becomes a leak-scan needle — see below.

**Three things that make `main.typ` free of `if`s.** `resolve` computes
`data["sections"]`, the list of sections that actually have content, and the
template filters it into columns. `resolve` stamps `meta.profile` into the
artifact *after* validation, so it is a property of the build and not in the
schema. `resolve` drops `projects` from `sections` for the `page` layout so
nothing renders twice.

---

## The private-data guarantee

Two profiles:

| | `--profile full` (default for `pdf`, only option for letters) | `--profile public` (forced for `export`) |
|---|---|---|
| `private.yaml` | Merged in, if present | **Ignored entirely**, even if present |
| `private: hidden` contact | Real value | Contact dropped completely |
| `private: refine` contact | Refined value | Committed value kept |

Four layers, each independent:

1. With a home, private data and applications are not in the working copy at
   all - `home set` refuses a folder inside the repository. Without one,
   `.gitignore` blocks `data/private.yaml`, `assets/private/`, and the
   gitignored parts of `applications/*/`. `build/` and `out/` are ignored
   either way.
2. Committed data holds placeholders only — a broken `.gitignore` still leaks
   nothing, and there has never been a real phone number in git history.
3. `resolve` stamps `meta.profile`. `export` re-reads the artifact and refuses
   to publish anything not `public`; the website's Hugo template fails its
   build on the same condition. Enforced on both sides of the repo boundary.
4. `check-clean` greps text artifacts for every value in `private.yaml`.

**How `check-clean` chooses its needles** (`check._private_needles`):

- Every leaf string in `private.yaml`, plus a digits-only form of anything
  with ≥7 digits (catches a phone number reformatted into a `tel:` URL).
- Minus anything shorter than 4 characters.
- Minus anything that already appears verbatim in a committed
  `data/cv-*.yaml`. A value the public data already contains cannot be a leak.
  This is load-bearing: `address.city` is "Karlsruhe", the CV publishes
  "Karlsruhe, DE", and without this rule `export` would refuse to publish.
- Minus the whole subtree under any top-level key in `NOT_SECRET`
  (`signature`, `documents`). Those are a manifest of gitignored files —
  paths and labels — not secrets. "Masterzeugnis" is printed in the letter
  itself; scanning for it would report a leak on every build.

**Add a key to `NOT_SECRET` when** the value is a path to a secret or a public
label, and would legitimately appear in a build artifact. Do not add it for an
actual private value.

`export` runs `check-clean` over exactly the files it wrote. Standalone
`cvforge check-clean` scans `build/` and `out/`, which after any full-profile
build legitimately contain the phone number — so on its own it is a check for
public builds, and a "LEAK" in `build/cv-en.json` after `cvforge pdf` is
expected, not a bug. PDFs are compressed and cannot be grepped; `export`
covers them by asserting the artifact they were rendered from is public.

If `private.yaml` does not exist, everything builds with placeholders and one
note. A fresh clone and CI need no special-casing.

---

## The home

Gitignored files in a working copy exist on one machine and are backed up
nowhere. The home moves everything personal - `private.yaml`, the signature,
the certificates, every application - into a folder of its own, normally one
OneDrive syncs, so a second machine has it and a deletion can be undone.

`paths.configured_home()` reads, in order: `$CVFORGE_HOME`, then
`cvforge.local.toml` (`home = '<dir>'`, a TOML literal string so a Windows
path needs no escaping, written by `cvforge home set`). Neither → the
repository is the home, which is exactly the pre-home layout, so a fresh clone
and CI need nothing. Everything downstream goes through `paths`:

- `APPLICATIONS`, `PRIVATE`, `PRIVATE_ASSETS` move with the home;
  `APPLICATION_TEMPLATE` never does - it is code.
- `private_path(rel)` resolves `signature` and `documents[].file` against the
  home (`PRIVATE_BASE`), or the repository without one.
- `bundle(slug)` is `application(slug)/send`, so what was sent sits next to
  what it was made from.

**A configured but missing home is an error**, `paths.HOME_PROBLEM`, raised by
`cli.main` for every command but `home`. Falling back to the repository would
quietly scaffold the next application where the other machine never sees it.

**Typst cannot read the home.** `--root .` confines it to the repository, so
`letter._typst_visible` copies a signature outside it to
`build/private/signature.<ext>` and the artifact points there. Nothing else
Typst reads is personal: attachments are copied by `apply` in Python.

**Schema hints.** Application files start with `$schema=../../schema/...`. In
the repository that is `schema/`; in the home it is `<home>/schema/`, a mirror
`home.sync_schema()` refreshes from `new`, `check` and `home set`. Same hint,
every machine, whatever the repository's path there.

`home.py` writes only `cvforge.local.toml` and the mirror. It never moves
data: `cvforge home` lists what is still only in the repository, and moving it
is the user's job (see [Guardrails](#guardrails)).

---

## The resolve step

`resolve.resolve(lang, profile)` → `load_yaml` → `validate_against` (JSON
Schema, with `oneOf` branch errors expanded) → `merge_private` → `derive`.
`write` serialises to `build/cv-<lang>.json`, sorted keys, UTF-8.

`derive` does: `clean` (collapses the double spaces YAML folding leaves),
labels, `meta.profile`, skill items normalised to `{name, rating, note}`,
`start_display`/`end_display`/`ongoing` on every dated entry, the education
`meta_line`, `projects_layout` handling, `url_label` derived from `url`, and
`sections`.

`dates.py`: `DATE_RE` accepts `YYYY` and `YYYY-MM` only. `DAY_RE` accepts
`YYYY-MM-DD` only, for the letter dateline. Deliberately separate patterns so
each schema says exactly what it means.

`i18n.py`: `LABELS` is emitted into every CV artifact and copied to the
website. `LETTER_LABELS` is a separate table for exactly that reason — a
letter's vocabulary has no business on the website.

---

## Cover letters

### Data flow

`letter.resolve_letter(slug)` → validate `letter.yaml` against
`schema/letter.schema.json` → check `meta.slug` matches the directory → call
`resolve.resolve(lang, "full", source=paths.cv_source(lang, slug))` for the
sender → `private_letter()` for address, signature, documents → `derive`, then
stamp `meta.cv_source`. Writes `build/letter-<slug>.json`.

The artifact carries `attachments` (resolved `{label, file, lang_fallback}`)
even though Typst never reads it: `apply` reads it to copy files, so what gets
sent and what the Anlagen line claims come from one pass.

Letters have no `--profile` flag. A letter carries a postal address by
definition, and is never exported.

### Layout: DIN 5008 Form B

Geometry in `templates/letter/theme.typ`, which imports the CV theme and adds
one `letter` dictionary. The numbers that are not negotiable, because a
window envelope and a scanner assume them:

| Key | | |
|---|---|---|
| `page.margin` | left 25, right 20, top 12, bottom 20 mm | |
| `address.top` | `45mm` | Top of the address field, from the **paper's** edge |
| `body.top` | `98.46mm` | Where the subject line starts |
| `fold.first` / `.second` | `87mm` / `192mm` | Fold marks |
| `fold.punch` | `148.5mm` | Hole-punch mark |

**Positions are measured from the paper, not the flow.** The letterhead and
the address band are both `place`d absolutely and consume no flow height, so
neither can push the other down. The flow starts with `v(body.top -
margin.top)`. Fold marks are drawn in `page(background:)`, whose coordinate
frame is the page corner.

**The letterhead must fit in `address.top - margin.top` = 33 mm** and will not
make room for itself. Name at 18pt + tagline + one contact row fits; a wrapped
two-line row does not. `sender_contacts` in the letter is the knob; the
scaffold omits `location` because the return line already carries the address.
`service.compile_letter` warns if the page count is not 1.

**`meta.layout: compact`** is the opt-out, for letters that only travel as a
PDF. Letterhead, address band and body flow one after another, separated by
`letter.compact.address-gap` / `body-gap`; nothing is placed, `address.top`
and `body.top` are ignored, and the fold marks are dropped (`letter-template`
takes `folds:`). It frees roughly 30 mm. `din` stays the default, and the
artifact carries `meta.layout` so `main.typ` branches on data, not on inputs.

**`meta.justify: true`** sets the body in Blocksatz via `letter-template`'s
`justify:`. Typst hyphenates justified text in the document's `lang`, so the
letter's language must be right or German compounds open rivers of space.

The info block beside the address field uses `columns: (auto, 1fr)` with a
gutter, not a fixed label column — `reference_label` is the posting's own
wording, so its width is unknowable, and a fixed column once drew the value on
top of a label that outgrew it.

The signature image is fitted into a fixed `image-width × image-height` box
with `fit: "contain"`, because a tall scan with unconstrained height silently
pushes the letter to two pages.

### What is composed where

| Value | Source | Override |
|---|---|---|
| `subject` | `subject_prefix + job.title [– reference_label reference]` | `subject:` |
| `salutation` | `labels.salutation_default` | `recipient.salutation` (free text: German forms of address need a gender the data does not carry) |
| `info` | `job.reference` (labelled) and `job.source` (a full phrase) | — |
| `closing` | `labels.closing` | `closing:` |
| `enclosures` | `file_cv` label, then each attachment's label | `enclosures:` |
| `date_display` | today, or `meta.date` | — |
| `return_line` | `name · street · postal_code city` from `private.address` | — |

`reference_label` is per application, not per language: every portal has its
own word (*Kennziffer*, *Referenznummer*, *Job-ID*). One value feeds both the
info block and the subject so they cannot disagree.

The structured `address` in `private.yaml` exists because DIN 5008 needs the
parts on separate lines and the CV stores one flat string. Splitting the flat
string on commas would work until an address had a comma in it.

### Attachments

Declared once in `private.yaml` under `documents:` as `{id, file, label}`,
picked per letter by id. `file` and `label` each take a string or a
`{de:, en:}` mapping (`_per_lang`), which covers one-file-one-name,
one-file-two-names (bilingual document) and two-files-two-names (issued per
language). A mapping missing the letter's language falls back to `en`, then
the first value, and sets `lang_fallback` — surfaced as a build note and a
`check` warning, not a refusal, because the fallback is still a real document.

A one-off `{file, label}` in a letter is resolved relative to the application
directory. Its `file` is a plain string on purpose: an application has one
language, so a second branch could never be reached.

**Missing files split by command.** `letter` builds regardless — it needs only
labels, and blocking a draft helps nobody. `apply` collects every attachment
with `file: None`, refuses with all of them named, and does so *before*
clearing the bundle so a failed run leaves the last good folder intact.
`check` reports a declared file missing from disk once per document
(`_check_documents`), and id/edition problems once per letter
(`_check_attachments`).

`apply` names files `NN_<Name>_<Label>.ext` via `service.send_name` and
`service.slugify_name` (umlauts transliterated, apostrophes dropped). Letter = 01,
CV = 02, attachments from 03 in listed order. The folder is emptied first so a
dropped attachment cannot linger. Copies are `shutil.copyfile`, byte-exact,
which is what preserves digital signatures on certificates — merging or
re-saving would break them.

**Once sent, `send/` is the record.** `apply` refuses (`service.sent_on`) when the
dossier has an `applied` date or a status in `check.SENT`, because emptying and
rebuilding the folder would replace what the employer received with what the
sources produce today - a later base CV, a different build date. `--force`
overrides it; `cvforge letter` still builds a draft to look at.

`cvforge letter` writes to `out/letters/<slug>.pdf`, outside the bundle, so a
draft rebuilt after `apply` cannot leave a stale numbered letter beside a fresh
unnumbered one.

### Live preview

Tinymist's `--input` flags in `.vscode/settings.json` are workspace-global and
cannot name a slug. `templates/letter/main.typ` therefore defaults to
`build/letter-preview.json`, and `cvforge dev --letter <slug>` mirrors the
resolved artifact there on every change. The template prefers `doc.meta.lang`
over `--input lang`, which says `en` regardless of which letter is open.

### Per-application CV

`cvforge new <slug> --cv` copies `data/cv-<lang>.yaml` to
`applications/<slug>/cv.yaml` (schema hint rewritten to `../../schema/`, a
header comment added). A full copy, not a patch: an application is a snapshot
of what was sent, and the base CV feeds the website, so tailoring must never
happen in `data/`.

- `paths.cv_source(lang, slug)` is the **only** place the choice is made: the
  override if the file exists, else the base. Letter, `apply` and `check` all
  go through it.
- `resolve.resolve/write` take `source=` (and `write` takes `target=`). The
  override gets the same validation and the same `merge_private` as the base -
  it is a copy with the same contact ids, so `private.yaml` just works.
- The letter artifact carries `meta.cv_source` (for the reader; in a home it
  is an absolute path). `apply` asks `paths.cv_source` again rather than
  parsing it back, so the letterhead and the attached CV come from one file.
- A tailored CV resolves to `build/cv-app-<slug>.json`, never over
  `build/cv-<lang>.json` (which the base CV's Tinymist preview reads), and is
  rendered with `--input artifact=/build/cv-app-<slug>.json`.
- `export` never passes `source=`, so an override cannot reach the website.
- `check` validates an override and runs the photo/image/id checks on it, but
  not the tag check - that would only repeat the base CV's warnings.

`apply` warns when the CV has more pages than `service.expected_cv_pages` (1, or 2
with `projects_layout: page`), and ends with a fixed-format `summary:` line
that the `/new-application` skill parses. Change that format and the skill
together.

### The dossier

`dossier.yaml` is read by nothing that renders. `check._check_dossiers`
validates it against `schema/dossier.schema.json` (a failure raises, as for a
letter) and warns about what makes it useless later: text from the old
scaffold (`TEMPLATE_REMNANTS` - "Anna Beispiel" and an invented applied date
once survived unedited and read as facts), no `summary`/`keywords`, a sent
`status` with no `applied` date or the reverse, a `posting.archive` that does
not exist or has no `posting.fetched`, files in `posting/` that
`posting.archive` does not name (a posting dropped in by hand is invisible to
whoever reads only the dossier), an `approach.based_on` naming no application.
`check._check_timeline` adds what breaks the dashboard's links: a `with` name
that is not in `contacts`, a `track` with no `tracks` entry, an event `files`
path that does not exist, and a `planned` entry whose day has passed.

**Timeline entries are structured.** Besides `date` and a one-line `event`:
`time`, `kind` (submitted, call, interview, … - `build` for CVForge's own
entries), `channel`, `with` (participants, by contact name), `track`, `notes`
(what was said - Markdown, "- " lists) and `files` (relative to the
application, e.g. `recv/` for documents received). `planned: true` marks
something ahead - an appointment, a deadline, a promised answer - and
`approx: true` an estimated date. When it happens, the same entry is updated
(`update_event`), not a second one added. The rule for where text goes: what
was said at an event in that event's `notes`; facts about a person in their
contact `notes`; what concerns the application as a whole in the dossier
`notes`. One fact, one place.

**Tracks** are optional processes inside one application, each with its own
status (`proposed` … `moved`): the clients a placement agency proposes you to,
or the other posting a company moved you to. Events name one with `track`.
The application's `status` stays the relationship with the company applied
to. A contact working for someone else (the client's interviewer) has `org`.

The scaffold therefore ships every value empty; `new` adds only a dated
"Created" timeline entry. `posting.archive` is relative to the application
directory, like a one-off attachment, so it survives the home moving.

Title, language, reference and attachments are deliberately not in the
dossier - `letter.yaml` has them, and two copies would drift. The one
exception is `role.title`, for an application that has no `letter.yaml` (sent
before CVForge, only the PDFs archived); `list` falls back to it.

`cvforge list` reads dossier and letter, sorts newest first by
`service.application_date` (`applied`, else the first timeline date, else the slug's
`YYYY-MM`), and with `--match` keeps applications whose keywords or summary
contain any of the words - not the job title, which an unwritten letter still
has from the scaffold. It filters but does not re-rank: the CV
and letters improve with each application, so recency stays the order and
the hit count is printed beside it.

### Tracked vs. not

Nothing under `applications/` is tracked except `_template/`, and with a home
the applications are not in the repository at all. Letters and tailored CVs
are drafts for one employer; dossiers, postings and attachments are
third-party personal data, copyrighted text and work samples. The scaffold's
`dossier.example.yaml` is tracked, the same pattern as `private.example.yaml`.
If a change needs a test application, use a scratch home or a scratch slug and
delete exactly that afterwards.

### The /new-application skill

`.claude/skills/new-application/` turns a markdown brief from the
letter-writing chat into a built application: scaffold, fill `letter.yaml` and
`dossier.yaml`, apply the brief's *confirmed* CV changes to the tailored copy,
`apply`, look at the PDFs, report. `brief-format.md` there is the contract for
the brief; `field-mapping.md` maps it onto the YAML. The skill changes layout
knobs (`justify`, `compact`) to fit a page but never the wording. A brief
without a postal address gets one looked up - the office in the job's city,
else the headquarters, from the imprint or an official register - and the
report flags it for confirmation.

`.claude/hooks/protect_private.py` (registered in `.claude/settings.json`)
blocks Write/Edit onto `private.yaml` and the private folder - in the
repository and in the home, which it reads from `cvforge.local.toml` itself -
and shell commands that would copy, move, delete or redirect onto them, or
delete the home or its `applications/` - the incident described under
[Guardrails](#guardrails). Reading is still allowed. It matches any
`private.yaml` and any `/private/` path component in a write command, so a
command like `ls build/private && sed -i …` is blocked too; split it.

---

## Styling the CV

Almost everything is in `templates/pdf/theme.typ`. A handful of constants are
load-bearing:

- The timeline rail is **one `grid.vline` spanning the whole grid**, not a
  segment per entry. That is what makes it survive a page break.
- `timeline.date-pad` keeps the node circle — which sits on the column
  boundary — off the date text.
- `timeline.node-dy` aligns the circle to the first baseline of the title. It
  is calibrated against `timeline.title-size`; retune it if you change that.
- `chip.outset` grows the chip background without affecting layout, so a line
  of chips keeps the height of a line of text.
- The contact row **packs its own lines** (`contact-row` measures each item and
  decides the breaks). To Typst's line breaker a `|` separator is just more
  inline content, so a wrapped row kept whichever separator landed at the end
  of a line — a divider dividing nothing.
- `icons.typ` wraps `@preview/fontawesome`, which maps names to code points but
  renders from the committed desktop OTFs — hence `--font-path assets/fonts`
  on every compile. `FALLBACK = true` draws stub circles without the fonts.

### The two-column layout

`MAIN-SECTIONS` and `ASIDE-SECTIONS` in `main.typ` decide which section goes
where. Geometry is `theme.sidebar`:

- **The sidebar is narrow on purpose** (33 mm column, 4 mm pad, so 29 mm
  content). Chips wrapping inline need ~45 mm; stacked they fit in 28. The
  main column holds the tall content, so every millimetre the sidebar takes
  costs *more* height than it saves. Widening it back to 45 mm pushes the CV to
  a second page.
- `header.photo-size` (28 mm) is independent of `sidebar.width`.
- **`sidebar.gutter` and `sidebar.pad` must stay equal.** The rule is drawn at
  the start of the sidebar column; `gutter` is the air to its left and `pad` to
  its right. When they were one value the rule read as a border stuck to the
  content.
- `sidebar.chip-layout`: `wrapped` (default) is never taller than `stacked` for
  the same content; it saves ~17 mm with the current data, which is what makes
  room for `interests`.

The aside starts below the header, so it lines up with the first section
heading whether or not there is a photo.

### The projects page

`meta.projects_layout: page` gives projects a full-width page: the same
timeline rail, text on the left, a screenshot on the right. Two keys size it:

| Key | Value | |
|---|---|---|
| `projects.image-width` | `50mm` | Width of the image column |
| `timeline.aside-gap` | `6mm` | Text → image |

The text column is `1fr`. On A4 with the current margins:

```
176.0mm page content (210 − 2 × 17)
 −17.4mm timeline dates (theme.timeline.date-col, 5.2em at 9.5pt)
 − 5.0mm rail gutter    (theme.timeline.gutter, 1.5em)
 −50.0mm image          (theme.projects.image-width)
 − 6.0mm gap            (theme.timeline.aside-gap)
 =97.6mm text
```

An entry with no `image` still reserves the column so every entry's text is
the same width. A single-year entry (`start == end`) prints the year once and
is nudged by `timeline.single-date-dy` to centre on its node. The footer
numbers pages from page 2, so the projects page shows `2 / 2` and page 1 stays
clean; use `counter(page).final()` in `template.typ` for `1 / 2` too.

### Fitting on one page

With `projects_layout: omit` both CVs fit one page; with `page` they are two.
`cvforge pdf` prints the count. **Check German first** — it runs longer. The
knobs, in order: `timeline.row-gutter`, `h1.above`, `leading`, `size`. Do
**not** shrink `timeline.date-col`: at 4.5em "Mar 2026" wraps. If the CV
overflows, the sidebar rule continues onto page two as a stub — a symptom, not
a separate bug.

### Level bars

`components/bars.typ` renders a fixed-width bar for `rating` (1–5) beside a
skill or language; rated rows are padded by `chip.inset.y` so they keep the
chip rhythm. A rated skill and a spoken language are the same shape and share
the component.

---

## Publishing to the website

`cvforge export --to <site>` refuses unless `<site>/config/_default/hugo.yaml`
exists. It resolves both languages as `public` (not overridable), re-reads each
artifact and refuses if `meta.profile != "public"`, copies them to
`data/cv/{en,de}.json`, compiles public PDFs into `static/files/`, and runs
`check-clean` over exactly those files. The public PDFs never touch `out/`, so
the full-profile PDF is not silently replaced.

**Why a file copy rather than automation.** CVForge is private. Anything that
pulls — a submodule, a CI fetch — needs a token in the public repo's secrets,
breaks for forks, and makes a public build depend on a private repo staying
reachable. The site only deploys on a published release, so automating the copy
would not save a step anyway.

Web presentation is the Portfolio repo's (`layouts/partials/cv.html`,
`assets/css/custom.css`). This repo owns content; that one owns look.

---

## The MCP server

`cvforge-mcp` (`src/cvforge/mcp_server.py`, extra `mcp`) lets Claude Desktop
read past applications, draft new ones and build them. Claude Desktop starts it
over stdio; it opens no port and makes no request. `cvforge mcp-config` prints
the config entry for the machine it runs on.

**Privacy is drawn at the tool result.** Claude runs remotely, so whatever a
tool returns is conversation content. Three independent layers:

1. **By construction.** Only resolve/letter read `private.yaml`. No tool returns
   contents of `build/`, `send/` or the private folder; builds return numbers,
   file names, warnings. No images - the user decided against even masked
   previews, which is why the layout report exists.
2. **The output filter.** `tool()` serializes every result and every error
   message and scans it with `check._private_needles()` - recomputed per call.
   A hit raises "Withheld" naming the trail (`contacts.phone.value`), never the
   value. Exceptions of any kind pass through the same filter.
3. **No dangerous verbs.** No delete, no `force`, no export; slugs must match
   `SLUG_RE` and resolve directly under `APPLICATIONS`; inbox files are bare
   names. Writes: `letter.yaml`, `cv.yaml`, `dossier.yaml`, `posting/`,
   appends to `guidance/learnings.md`, and `<home>/dashboard.html` - rewritten
   by `tool()` after every non-read tool, never returned.

**Tools** - read-only: `status`, `list_applications`, `get_application`,
`get_base_cv`, `get_reference`, `list_documents`, `read_inbox`, `get_guidance`.
Drafting: `create_application`, `import_posting`, `edit_file`,
`update_dossier`, `build_draft`, `remember`. Decisive (`destructive_hint`, so
Desktop asks): `apply`, `mark_sent`, `log_event`, `update_event`,
`set_track`. One prompt, `new_application`, in Desktop's "+" menu.

- `log_event` takes the structured fields (`participants` is written as
  `with`) and inserts in date order, so a late-logged event does not land
  behind a planned one. `update_event` finds one entry by `date` plus a
  substring of its event and replaces the fields given - the way a planned
  entry is completed. Both return `check._check_timeline`'s warnings for the
  dossier, e.g. a participant who is not a contact yet. `set_track` upserts a
  track; `track_status` on the event tools moves it.

- `get_application` returns every requested part: one that does not exist is
  `null`, with the reason under `unavailable` - a silently missing key read as
  a bug in testing. It resolves `title`/`company` with their source
  (`service.application_title`), because the title lives in letter.yaml and a
  reader of the dossier alone wonders where `list_applications` got it.
- A `brief.md` is the frozen hand-over an application was built from and is
  never updated; `INSTRUCTIONS` tell Claude to trust the dossier over it.
- `edit_file` is exact-unique string replacement, then a real
  `letter.resolve_letter` (plus CV validation); any error restores the file.
  Refused once sent, like `apply`.
- `update_dossier` deep-merges with ruamel.yaml so comments survive; it refuses
  `status`, `applied`, `timeline`, `tracks`, which only the decisive tools set -
  recording a submission or news is always its own, approved call.
- `build_draft` writes `out/letters/<slug>.pdf` and `out/drafts/<slug>-cv.pdf`,
  never `send/`, and returns the **layout report**: `templates/pdf/components/
  marker.typ` leaves `place`d metadata (zero size - renders are byte-identical
  with and without it) where each flow ended, how tall the letterhead is, and
  how many lines the subject and - compact layout only, where it is in the
  flow - the recipient take (`lines-marker`); `service._markers` reads it with
  `typst eval 'query(...)'`, falling back to `typst query` on a Typst without
  `eval`, and reports `room_mm` or `overflow_mm`.
- The server's `INSTRUCTIONS` carry the workflow rules the skill used to:
  never reword approved body text, `apply`/`mark_sent` only on the user's
  word, look up and cite a missing address. To fit a page Claude may, without
  asking, shorten a wrapping `subject:` (reference first - the info block
  shows it), drop the recipient's department/person in compact layout, and
  set `justify`/`compact`; it tells the user what it changed.
- **Guidance** stands in for a Claude Project's library and memory, which a
  local Desktop session does not have. `<home>/guidance/` holds
  `instructions.md` and `snippets.md` (the user's; no tool writes them) and
  `learnings.md`. `get_guidance` returns all three (missing ones `null` +
  `unavailable`); the `new_application` prompt inlines them, through `_guard`
  by hand since prompts bypass `tool()`. `remember` appends one dated line and
  is a drafting tool on purpose - the user chose no approval prompt and curates
  the file by hand. It guards the text *before* writing, so a private value
  cannot reach a file every later chat reads back, and it has no edit or
  delete counterpart.

**stdout is the protocol.** mcp 2.x diverts fd 1 to stderr while serving, and
`service._run` captures typst's output; the `tool()` wrapper additionally
redirects `sys.stdout`/`stderr` per call and returns note/warning lines as
`log`. Never print from server code outside a tool call.

Postings reach the server through `<home>/inbox/` (a chat attachment never
reaches a local process); `import_posting` moves one into `posting/`.

---

## The dashboard

`cvforge dashboard [--open]` writes `<home>/dashboard.html`: an overview (next
dates, what needs attention, the pipeline, an activity strip), one page per
application (tracks, the timeline with participants and expandable notes,
people, files) and a people view across applications. Read-only by design;
everything is still written through the CLI or the MCP tools.

- **Same split as the CV.** `dashboard.collect` derives every value - date
  labels, "next step", overdue flags, strip positions, each contact's activity,
  notes split into paragraphs and lists - and embeds the JSON in the template
  at `/*CVFORGE_DATA*/null`, with `<`, `>`, `&` escaped so a note cannot close
  the `<script>`. The page's JS only routes (`#/`, `#/app/<slug>`,
  `#/people`) and draws, and it sets every value as text, never HTML: the
  dossiers hold other people's writing.
- **Local by construction.** It holds recruiters' details and interview notes,
  so it lives in the home beside the dossiers (OneDrive syncs it to the
  laptop) and is gitignored when the repository is the home. No tool returns
  it. Links are relative to the home, so they work on every machine; folder
  links open the browser's file listing.
- **Always current.** The MCP `tool()` wrapper calls `dashboard.refresh()`
  after every non-read tool. A failure there is a warning in the log, never a
  failed tool - the change it follows is already written.
- **Thresholds** are module constants: `STALE_DAYS` (applied, no news →
  attention), `AHEAD_DAYS` (how far "Next up" looks), `STRIP_BACK`/
  `STRIP_AHEAD` (the activity window).
- **The logo** comes from `assets/logo/`: `write` embeds `cvforge-favicon.svg`
  as a data URI and `cvforge-mark.svg` into a `<template>` the header clones.
  The mark's colours are `var(--cvf-*, fallback)`, which `.brand-row` sets
  from the page's theme; hovering it plays the strike on the mark's
  `cvf-swing`/`cvf-sparks` classes.

### The logo

"The strike": a hammer meets a page, sparks fly, the page's lines are
written. `uv run assets/logo/build.py` (a PEP 723 script; fontTools comes
with it, not with the project) writes every SVG from one geometry. The
wordmark is outlined from `assets/fonts/Inter-Bold.otf`, because an SVG shown
as an image - a README, a favicon - cannot load a font. The README header is
two files, chosen by `<picture>` per GitHub theme; its loop is CSS inside the
SVG, which GitHub plays, and `prefers-reduced-motion` shows the resting frame.
Every class and keyframe is prefixed `cvf-` so an inlined copy cannot collide
with the page that inlines it. Inline SVG styles are global, so never inline
two different logo files into one page.

---

## Troubleshooting

**Icons are blank, or `unknown font family: font awesome 7 free solid`**
The compile is missing `--font-path assets/fonts`. The CLI always passes it;
by hand, add it. In VS Code, `tinymist.fontPaths` in `.vscode/settings.json`.

**`error: file not found (searched at /build/cv-en.json)`**
Either the resolve step has not run, or Typst was invoked without `--root .` —
the leading slash in `json("/build/…")` is root-absolute.

**The typeface looks wrong**
Typst fell back silently because it could not find Inter — a missing
`--font-path`.

**`cvforge pdf` prints no page count**
`service.page_count` byte-scans for `/Type\s*/Pages` then `/Count`. Typst 0.14 writes
`/Type /Pages` with a space where 0.13 did not; if the pattern ever stops
matching it returns `None` and the count is silently omitted, which is how a
regression to two pages hides.

**`check-clean` reports leaks in `build/` after a normal build**
Expected. See [the private-data guarantee](#the-private-data-guarantee).

**Editing YAML in VS Code shows "Property X is not allowed" after a schema
change** — the YAML extension caches the schema. Reload the window.

---

## Verification recipe

There is no test suite. This is what proves a change is safe; run all of it.

```bash
# Lint
uv run ruff check src/ && uv run ruff format --check src/

# Nothing about the CV changed
uv run cvforge check                      # same warnings as before, no errors
uv run cvforge pdf --lang en              # note the page count
uv run cvforge pdf --lang de              # German is the tighter one

# The publish guarantee still holds - run against a stub site, no real repo needed
mkdir -p /tmp/site/config/_default && touch /tmp/site/config/_default/hugo.yaml
uv run cvforge export --to /tmp/site     # must end with "clean"
rm -rf /tmp/site

# Letters run in a scratch home, so the real one is never written to.
# (PowerShell: $env:CVFORGE_HOME = "...")
export CVFORGE_HOME="$(mktemp -d)"
uv run cvforge home                       # ok-lines for applications/, missing private.yaml

# A letter end to end
uv run cvforge new scratch-verify --lang de
uv run cvforge letter scratch-verify      # "(1 page)", placeholder-address note
uv run cvforge apply scratch-verify       # <home>/applications/scratch-verify/send/, "cv source data/cv-de.yaml"

# A tailored CV: edit the copy's profile, then apply
uv run cvforge new scratch-cv --lang en --cv
uv run cvforge apply scratch-cv           # "cv source <home>/applications/scratch-cv/cv.yaml"
git diff --quiet -- data/ && echo "base CV untouched"

rm -rf "$CVFORGE_HOME" && unset CVFORGE_HOME
rm -f build/cv-app-scratch-cv.json build/letter-scratch-cv.json build/letter-scratch-verify.json

# The MCP server, end to end over stdio, in its own throwaway home
uv run --extra mcp python -m cvforge.mcp_selftest   # "N/N passed", incl. the leak test
                                                    # (it covers the dashboard page too)
rm -f out/letters/scratch-verify.pdf out/letters/scratch-cv.pdf

# A home that is set but missing refuses, rather than falling back to the repo
CVFORGE_HOME=/nonexistent uv run cvforge check   # "error: $CVFORGE_HOME sets the home to ..."

# Nothing private is tracked
git status --short --untracked-files=all  # no dossier.yaml, posting/, attachments/, private files
git check-ignore -v data/private.yaml assets/private/signature.png cvforge.local.toml
```

To exercise a signature or a document, write a fake `private.yaml`, a
`private/signature.png` and a `private/documents/<x>.pdf` into the scratch home
first - never into the real one.

If a change touches the leak scanner, the letter's needle count printed by
`export` (`scanned N text artifact(s) for M private value(s)`) is the number
to watch: it should not change unless you changed `private.yaml`.

If a change touches layout, render a page to PNG and look at it:

```bash
typst compile templates/letter/main.typ /tmp/p.png --root . --font-path assets/fonts \
    --input slug=<slug> --format png --ppi 150
```

For the letter, hold the result against DIN 5008: address field top at 45 mm,
fold marks at 87 / 192 mm, one page.
