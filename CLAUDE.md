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
- [The resolve step](#the-resolve-step)
- [Cover letters](#cover-letters)
- [Styling the CV](#styling-the-cv)
- [Publishing to the website](#publishing-to-the-website)
- [Troubleshooting](#troubleshooting)
- [Verification recipe](#verification-recipe)

---

## Guardrails

**Never overwrite, move or delete `data/private.yaml` or anything under
`assets/private/`.** They are gitignored and there is no copy anywhere — a
deleted signature scan or certificate is gone. This has happened once, from a
test that ran `cp data/private.example.yaml data/private.yaml` and a cleanup
that ran `rm -rf data/private.yaml assets/private`. The user's real
`private.yaml` was only recovered because VS Code happened to have a local
history snapshot; the signature scan had to be re-scanned.

For tests:

- Never create `data/private.yaml` if it exists. Read it if you need to know
  what is in it; do not print its values.
- Use a scratch application slug (`cvforge new scratch-…`) and delete only
  that directory afterwards.
- Never write to `assets/private/`. If a test needs a document, point a
  scratch letter's one-off `{file, label}` entry at a file under the scratch
  application's own `attachments/`.
- Cleanup commands must name the files they created, not patterns. Never
  `rm -rf` a directory you did not create in the same session.

`build/` and `out/` are generated and safe to delete. `out/applications/<slug>/`
is emptied by `apply` by design.

---

## Architecture

```
data/cv-en.yaml ─┐
data/cv-de.yaml ─┼─→ build/cv-<lang>.json ──┬─→ out/cv-<lang>.pdf            (profile=full)
data/private.yaml┘   (the resolved artifact) └─→ the website's data/ + static/  (profile=public)
   (gitignored)

applications/<slug>/letter.yaml ─┐
data/cv-<lang>.yaml (sender)    ─┼─→ build/letter-<slug>.json ─→ out/letters/<slug>.pdf
data/private.yaml (address, sig) ┘                              ─→ out/applications/<slug>/  (apply)
```

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
applications/        One directory per application. _template/ is the scaffold.
  <slug>/letter.yaml       tracked
  <slug>/dossier.yaml      gitignored - the posting, recruiter contacts, status
  <slug>/posting/          gitignored - the archived posting
  <slug>/attachments/      gitignored - one-off files for this job
schema/              JSON Schema for cv, letter and dossier; wired into VS Code.
src/cvforge/
  paths.py             Every repo path, resolved once. Add path helpers here.
  resolve.py           CV: load -> validate -> merge private -> derive -> write.
  letter.py            Letter: the same shape, plus attachments.
  check.py             `check` (content warnings) and `check-clean` (leak scan).
  dates.py             "YYYY"/"YYYY-MM" for the CV; "YYYY-MM-DD" for the letter.
  i18n.py              LABELS (CV, shipped to the website) and LETTER_LABELS.
  cli.py               argparse, typst invocation, the commands.
templates/pdf/       The CV renderer.
  theme.typ            Every design token. No magic numbers anywhere else.
  template.typ         Page geometry and set/show rules.
  icons.typ            Font Awesome behind one function; FALLBACK flag.
  components/          header, contact row, chips, bars, timeline, sidebar.
  sections/            One module per CV section.
  main.typ             Assembly only.
templates/letter/    The letter renderer. Imports ../pdf/ for theme, icons and
                     the contact row, so the two cannot drift apart on look.
assets/
  fonts/               Committed, SIL OFL. Inter, JetBrains Mono, Font Awesome 7.
  projects/            Screenshots for the projects page.
  private/             GITIGNORED. signature.png and documents/.
build/  out/         Generated. Both gitignored.
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
outside the repo). `_compile` appends the page count as `(N pages)`.

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

1. `.gitignore` blocks `data/private.yaml`, `assets/private/`, `build/`, `out/`,
   and the gitignored parts of `applications/*/`.
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
`resolve.resolve(lang, "full")` for the sender → `private_letter()` for
address, signature, documents → `derive`. Writes `build/letter-<slug>.json`.

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
`_compile_letter` warns if the page count is not 1.

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

`apply` names files `NN_<Name>_<Label>.ext` via `_send_name` and
`_slugify_name` (umlauts transliterated, apostrophes dropped). Letter = 01,
CV = 02, attachments from 03 in listed order. The folder is emptied first so a
dropped attachment cannot linger. Copies are `shutil.copyfile`, byte-exact,
which is what preserves digital signatures on certificates — merging or
re-saving would break them.

`cvforge letter` writes to `out/letters/<slug>.pdf`, outside the bundle, so a
draft rebuilt after `apply` cannot leave a stale numbered letter beside a fresh
unnumbered one.

### Live preview

Tinymist's `--input` flags in `.vscode/settings.json` are workspace-global and
cannot name a slug. `templates/letter/main.typ` therefore defaults to
`build/letter-preview.json`, and `cvforge dev --letter <slug>` mirrors the
resolved artifact there on every change. The template prefers `doc.meta.lang`
over `--input lang`, which says `en` regardless of which letter is open.

### Tracked vs. not

`letter.yaml` is tracked (your own writing; a company address is imprint
data). `dossier.yaml`, `posting/`, `attachments/` are not (third-party
personal data, copyrighted posting text, work samples). The scaffold's
`dossier.example.yaml` is the tracked counterpart, the same pattern as
`private.example.yaml`. The one unavoidable seam is the recipient's name in
the salutation.

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
`_page_count` byte-scans for `/Type\s*/Pages` then `/Count`. Typst 0.14 writes
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

# A letter end to end, on a scratch slug you delete afterwards
uv run cvforge new scratch-verify --lang de
uv run cvforge letter scratch-verify      # "(1 page)"
uv run cvforge apply scratch-verify       # numbered folder
rm -rf applications/scratch-verify out/applications/scratch-verify out/letters/scratch-verify.pdf

# Nothing private is tracked
git status --short --untracked-files=all  # no dossier.yaml, posting/, attachments/, assets/private/
git check-ignore -v data/private.yaml assets/private/signature.png
```

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
