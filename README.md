# CVForge

One CV, written once as data, rendered to two targets:

- **A4 PDF** for job applications — typeset with [Typst](https://typst.app)
- **The website** — the public CV data and PDFs, exported into the
  [Portfolio](https://github.com/dom-wuest/Portfolio) repo, which renders them
  on dom-wuest.de/about/

The content lives in `data/cv-<lang>.yaml`. Everything else is a renderer. Your
phone number and street address live in a gitignored file and never reach a
tracked file or the website.

```
data/cv-en.yaml ─┐
data/cv-de.yaml ─┼─→ build/cv-<lang>.json ─┬─→ out/cv-<lang>.pdf        (profile=full)
data/private.yaml┘   (the resolved artifact)└─→ the website's data/ + static/  (profile=public)
   (gitignored)
```

Both renderers read **only** `build/cv-<lang>.json`. Neither reads YAML, and
neither knows `private.yaml` exists. That is what lets a third target (a
plain-text version, JSON-LD, an ATS-friendly PDF) be added later without
touching the data.

**Cover letters** are the fourth target, and they work the same way — one YAML
per application, resolved to JSON, rendered by its own Typst template. They
read your name, contacts and address out of the CV rather than restating them,
so a letterhead cannot disagree with the CV stapled behind it. See
[Cover letters](#cover-letters).

---

## Contents

- [Quick start](#quick-start)
- [Commands](#commands)
- [Editing your CV — the dev loop](#editing-your-cv--the-dev-loop)
- [Private data](#private-data)
- [The YAML format](#the-yaml-format)
- [How to add an experience entry](#how-to-add-an-experience-entry)
- [Cover letters](#cover-letters)
- [Project layout](#project-layout)
- [Styling the PDF](#styling-the-pdf)
- [Publishing to the website](#publishing-to-the-website)
- [Troubleshooting](#troubleshooting)

---

## Quick start

### Prerequisites

Two tools. Both are single binaries.

| Tool | What for | Install |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python environment and the `cvforge` CLI | `winget install astral-sh.uv` · `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [typst](https://github.com/typst/typst) | Typesets the PDF | `winget install Typst.Typst` · `cargo install --locked typst-cli` |

Fonts are **committed to the repo** (`assets/fonts/`), so there is nothing to
install and the output is identical on every machine. See
[assets/fonts/README.md](assets/fonts/README.md) for what is there and why.

### Build

```bash
uv run cvforge pdf --lang en      # -> out/cv-en.pdf
```

That is the whole setup. `uv` creates the virtualenv and installs dependencies
on first run. The first Typst compile also downloads the `fontawesome` package,
which needs a network connection once.

---

## Commands

Everything goes through one CLI. There is no `just`/`make` — one tool fewer to
install, and identical behaviour on Windows, Linux and CI.

| Command | Does |
|---|---|
| `uv run cvforge pdf --lang en` | Resolve, then compile `out/cv-en.pdf` |
| `uv run cvforge export --to <site>` | Resolve both languages as public, then write the website's data files and PDFs |
| `uv run cvforge resolve --lang en` | Just the data step → `build/cv-en.json` |
| `uv run cvforge dev --lang en` | Watch `data/`, regenerate the JSON on every save |
| `uv run cvforge all` | The PDF for every language present |
| `uv run cvforge check` | Validate the data, report content warnings |
| `uv run cvforge check-clean` | Fail if a private value reached `build/` or `out/` |
| `uv run cvforge new <slug>` | Scaffold a new application — see [Cover letters](#cover-letters) |
| `uv run cvforge letter <slug>` | Build that application's cover letter |
| `uv run cvforge apply <slug>` | Build the send-ready folder: letter + matching CV |

Add `--lang de` for German. Add `--profile public` to any of them to build as
if `private.yaml` did not exist.

In VS Code the same commands are in the command palette under **Tasks: Run
Task** (`CV: Build PDF (en)` and friends).

---

## Editing your CV — the dev loop

**Recommended: the [Tinymist](https://marketplace.visualstudio.com/items?itemName=myriad-dreamin.tinymist)
VS Code extension.** It gives an in-editor live preview that updates as you
type, with click-to-jump between the source and the rendered page. It is in
`.vscode/extensions.json`, so VS Code offers to install it when you open the
folder, and `.vscode/settings.json` already points it at the bundled fonts.

Two halves, because Tinymist watches Typst files but knows nothing about YAML:

1. **Terminal** — `uv run cvforge dev --lang en`
   Watches `data/` and regenerates `build/cv-en.json` on every save.
2. **Editor** — open `templates/pdf/main.typ`, run **Tinymist: Preview** from
   the command palette.

Now: editing a `.typ` file updates the preview on keystroke; editing a `.yaml`
file regenerates the JSON, which the preview picks up a moment later.

Without Tinymist, `uv run cvforge dev --lang en --compile` also reruns
`typst compile` on every change, and you keep a PDF viewer open on
`out/cv-en.pdf`.

> Previewing the German CV: change both `tinymist.typstExtraArgs` and
> `tinymist.preview.sysInputs` in `.vscode/settings.json` from `en` to `de`.

---

## Private data

A CV for an application needs a phone number and a street address. A public
repo and a public website must not have them.

The rule here is that **it is impossible by construction, not by discipline**:
the committed `data/cv-<lang>.yaml` contains only placeholders, so there has
never been a real phone number in a tracked file, even in git history.

### Setup

```bash
cp data/private.example.yaml data/private.yaml   # gitignored
```

Then fill in the real values. One file, shared across all languages.

```yaml
contacts:
  phone:
    value: "+49 721 1234567"
    url: "tel:+491234567"
  location:
    value: "Musterstraße 1, 76131 Karlsruhe"
```

The keys are the `id` of a contact in `data/cv-<lang>.yaml`, and only `value`
and `url` can be overridden.

Two further top-level keys, `address` and `signature`, are read only by the
cover letter — see [Cover letters](#cover-letters). Both are optional and both
degrade to placeholders, so nothing here is required to build anything.

### The two profiles

| | `--profile full` (default for `pdf`) | `--profile public` (forced for `export`) |
|---|---|---|
| `private.yaml` | Merged in, if present | **Ignored entirely**, even if present |
| `private: hidden` contact | Real value | Contact dropped completely |
| `private: refine` contact | Refined value | Committed value kept |

Contacts declare which of two kinds of private they are:

```yaml
- id: phone
  value: "+49 000 0000000"
  private: hidden     # placeholder; vanishes from the web entirely

- id: location
  value: "Karlsruhe, DE"
  private: refine     # publishable as-is; private.yaml refines it for applications
```

`hidden` is for things the web must never see. `refine` is for things where the
public form is fine but the application wants more precision.

### The four layers

1. `.gitignore` blocks `data/private.yaml`, `build/` and `out/`
2. Committed data holds placeholders only — a broken `.gitignore` still leaks nothing
3. `resolve` stamps `meta.profile` into the artifact. `export` re-reads it and
   refuses to publish anything that is not `public`, and the website's Hugo
   template **fails its build** on the same condition — so the guarantee is
   enforced on both sides of the repository boundary, not merely trusted
   across it
4. `uv run cvforge check-clean` greps the generated artifacts for every value
   in `private.yaml`, including a digits-only form of the phone number

`export` runs `check-clean` over exactly the files it just wrote and refuses to
finish if anything matches. Publishing is a one-way action, so this is not
optional and not something you have to remember.

If `private.yaml` does not exist, everything still builds — placeholders are
used and one informational line is printed. A fresh clone and CI need no
special-casing, which is why the published artifacts are automatically safe.

---

## The YAML format

Full reference. `schema/cv.schema.json` enforces all of it, and VS Code shows
completions and errors as you type (needs the `redhat.vscode-yaml` extension,
which is in the recommendations).

### Three rules that bite

**1. Dates are quoted strings**, `"YYYY"` or `"YYYY-MM"`.

Precision is inferred from the length: `"2021-10"` renders as `Oct 2021`,
`"2023"` renders as `2023`. Quoting keeps the type predictable — unquoted,
YAML leaves `2021-10` a string but turns a full `2021-10-01` into a date
object, and the two look identical in a diff.

`end: null`, or omitting `end`, means ongoing → *Present* / *heute*.

**2. Quote anything YAML coerces.** `no`, `on`, `off`, `yes` become booleans.
`grade: 1.20` becomes the float `1.2`. Always `grade: "1.2"`.

**3. Store data, not presentation.**

```yaml
grade: "1.2"           # yes
grade_note: current

meta: "Current Grade 1.2"   # no
```

The renderers compose the display string. This is the rule that makes a second
renderer possible at all — the website needs the same facts in a different
shape.

Entry order in the file is display order. Nothing is sorted downstream.
Prose uses `>` (folded); reserve `|` (literal) for text needing real line breaks.
`cvforge check` catches all three mistakes.

### `meta`

```yaml
meta:
  lang: en                                  # must match the filename
  name: "Dominik Wüst"
  tagline: "M.Sc. Computer Science – …"
  photo: "assets/avatar.jpg"                # repo-relative; null for none
```

Set `photo: null` to build a version without a photograph — see
[Building without a photo](#building-without-a-photo).

### `contacts`

Display order is file order.

```yaml
contacts:
  - id: email               # join key with private.yaml, stable across languages
    icon: envelope          # Font Awesome name, used by BOTH renderers
    value: "kontakt@dom-wuest.de"
    url: "mailto:kontakt@dom-wuest.de"      # optional
  - id: github
    icon: github
    brand: true             # renders from the Font Awesome Brands font
    value: "dom-wuest"
    url: "https://github.com/dom-wuest"
```

| Key | |
|---|---|
| `id` | Required. Lowercase kebab-case. |
| `icon` | Required. Font Awesome icon name. |
| `value` | Required. The displayed text. |
| `url` | Optional. Makes it a link. |
| `brand` | `true` for `github`, `linkedin`, … (Brands font has no solid variant). |

**Write profile links as `linkedin.com/in/handle`, not just `handle`.** The
icon tells a human which platform it is, but the bare handle is not typeable
from a printed page, and ATS URL extraction matches on the domain rather than
on a username. Drop the `https://www.` — it is noise. Keep the full URL in
`url` so the PDF stays clickable.
| `private` | `hidden` or `refine` — see [Private data](#private-data). |

### `profile`

One folded paragraph.

```yaml
profile: >
  Computer Science graduate specializing in real-time computer graphics …
```

### `experience`

```yaml
experience:
  - id: fraunhofer-iosb
    role: "Research Assistant"
    org: "Fraunhofer IOSB"
    location: "Karlsruhe, Germany"     # optional; becomes the small meta line
    start: "2021-10"
    end: "2026-03"                     # null or omitted = ongoing
    highlights:                        # optional; rendered as bullets
      - >
        Applied pretrained computer vision models …
    tags: ["C++", "Qt", "OpenCV"]      # optional; rendered as chips
```

### `education`

```yaml
education:
  - id: msc-kit
    degree: "M.Sc. Computer Science"
    org: "Karlsruhe Institute of Technology (KIT)"
    start: "2023"
    end: null
    thesis: >                          # title only — the "Thesis:" label is added
      Automatic Shader Function Level of Detail …
    minor: "Electrical Engineering"    # optional
    specialization: "Computer Science" # optional
    grade: "1.2"                       # optional, quoted
    grade_note: current                # current | final | null
    tags: ["Computer Graphics"]
```

`thesis`, `specialization`, `minor` and `grade` are composed into one meta line
with ` – ` separators, skipping whatever is absent. `grade_note: current`
renders *Current Grade 1.2*; `final` renders *Grade 1.2*.

### `projects` *(optional)*

Where projects appear is a single switch in `meta`:

| `meta.projects_layout` | |
|---|---|
| `inline` *(default)* | In the main column with the other sections, as an ordinary timeline. |
| `page` | On its own full-width page after the CV — no sidebar, and room for a screenshot beside each entry. Still one document, so the running footer numbers it. |
| `omit` | Left out entirely. |

Note it is `omit`, **not** `off`: YAML 1.1 would read an unquoted `off` as the
boolean `false`. Deleting the whole `projects` key works too.

`image` is only read by the `page` layout — the other two have no room for it.

```yaml
projects:
  - id: path-tracer
    name: "Real-Time Path Tracer"
    role: "Solo project"               # optional; becomes the meta line
    summary: >                         # optional
      A Vulkan path tracer with ReSTIR direct lighting.
    start: "2024-05"
    end: null
    url: "https://github.com/dom-wuest/example"    # optional
    url_label: "github.com/dom-wuest/example"      # optional; derived from url
    url_note: "Code will be published after grading" # optional; shown when url is absent
    image: "assets/projects/path-tracer.jpg"       # optional; `page` layout only
    highlights: ["Wavefront path tracing …"]       # optional
    tags: ["Vulkan", "Slang"]
```

### `skills`

A **list of groups**, not a mapping — mappings do not guarantee order across
YAML libraries, and order is meaningful here.

Skills render in the sidebar directly above the spoken `languages` section, so
**do not name a group after that section**. A group called `Languages` sits
right under the `LANGUAGES` heading and reads as a mistake; in German the two
would be the identical word `Sprachen`. Use `Programming` / `Programmierung`.

```yaml
skills:
  - group: "Programming"
    items:
      - { name: "C++", rating: 5 }   # optional 1-5 bar
      - { name: "Python", rating: 4 }
  - group: "Graphics & GPU"
    items: ["Vulkan", "Slang", "GLSL", "CUDA"]   # bare names -> chips
```

An item is either a **bare name**, which renders as a chip, or a **mapping**
with an optional `rating` (1-5, draws a bar) and an optional `note` (a short
muted line beneath). Either one promotes the item out of the chip run and onto
a full-width row of its own. See [Level bars and notes](#level-bars-and-notes).

### `languages`

`level` is free text, already in the file's own language.

```yaml
languages:
  - name: "German"
    level: "native"
    rating: 5 # optional, 1-5
```

### Multilingual

`data/cv-en.yaml` and `data/cv-de.yaml` are independent files with identical
structure. Duplicated dates and ids are fine; schema contortions are not.

Language-dependent *renderer* strings — section headings, `Present`/`heute`,
month abbreviations — are **not** in the data. They live in
[src/cvforge/i18n.py](src/cvforge/i18n.py) and are emitted into the resolved
JSON, so neither renderer carries its own copy. To add a language: add a block
there, add `data/cv-<lang>.yaml`, done.

`data/cv-de.yaml` currently has real structure and dates but untranslated
prose, each marked `TODO übersetzen:` so it is obvious in the rendered PDF.

---

## How to add an experience entry

1. Open `data/cv-en.yaml` and find `experience:`.
2. Copy an existing entry. Entries render in file order — put it where you want
   it to appear, newest first.
3. Change `id` to something unique and lowercase, e.g. `acme-gmbh`.
4. Set `start` / `end` as **quoted** `"YYYY-MM"`. Omit `end` if it is ongoing.
5. Write `highlights` as folded (`>`) bullets — one achievement each.
6. List technologies in `tags`. They render as chips.

```yaml
  - id: acme-gmbh
    role: "Graphics Engineer"
    org: "ACME GmbH"
    location: "Berlin, Germany"
    start: "2026-04"
    end: null
    highlights:
      - >
        Built a Vulkan-based deferred renderer with clustered shading,
        cutting frame time by 40% on integrated GPUs
    tags: ["Vulkan", "C++"]
```

Then:

```bash
uv run cvforge check                # catches quoting and typo mistakes
uv run cvforge pdf --lang en
```

Do the same in `data/cv-de.yaml` to keep the German CV in step. Nothing forces
the two files to agree — that is deliberate.

---

## Cover letters

A CV is written once and reused. A cover letter is the opposite: one company,
one posting, one time. So a letter is a **sibling target**, not a new CV
section — its own YAML, its own schema, its own Typst entry point.

What it is *not* is a second copy of your identity. The name, tagline, contacts
and postal address in the letterhead are read from `data/cv-<lang>.yaml` and
`data/private.yaml`, the same files the CV uses. The letter YAML holds only
what is specific to the application.

Letters are never exported and never published. They are always built at
`profile=full`, which is why the letter commands have no `--profile` flag.

### Writing one

```bash
uv run cvforge new 2026-09-acme-rendering-engineer --lang de
```

That scaffolds:

```
applications/2026-09-acme-rendering-engineer/
  letter.yaml     the letter itself          TRACKED
  dossier.yaml    the posting, the people    gitignored
  posting/        the archived posting       gitignored
```

Date-prefix the slug and the directory sorts itself chronologically.

Fill in `letter.yaml`, then:

```bash
uv run cvforge check                                   # validates it too
uv run cvforge letter 2026-09-acme-rendering-engineer  # just the letter
uv run cvforge apply  2026-09-acme-rendering-engineer  # the folder to send
```

`apply` writes `out/applications/<slug>/` containing the letter and a freshly
built CV in the letter's language, named the way an upload form expects:
`Dominik_Wuest_Anschreiben.pdf` and `Dominik_Wuest_Lebenslauf.pdf` (or
`_Cover_Letter` / `_CV` for `lang: en`). The CV is rebuilt rather than copied
from `out/`, so the two documents in the folder are always the same vintage.

For the live preview, the letter equivalent of the CV's dev loop:

```bash
uv run cvforge dev --letter 2026-09-acme-rendering-engineer
```

then open `templates/letter/main.typ` and run **Tinymist: Preview**. Tinymist's
`--input` flags are set once for the whole workspace and cannot name a slug, so
the template reads `build/letter-preview.json` and the watcher keeps that file
pointed at whatever you are working on.

### What is tracked and what is not

`letter.yaml` is committed. It is your own writing, worth a history, and the
company's postal address on it is public imprint data.

`dossier.yaml` and `posting/` are not. A recruiter's name, email and phone are
someone else's personal data, and an archived posting is someone else's
copyrighted text — neither belongs in a history that outlives the application.
Nothing renders from the dossier; it exists so that three weeks later, when the
posting has been taken down and you are sitting in the interview, the facts are
still somewhere.

Archive the posting as a **PDF print, not a screenshot**. It keeps the text
selectable and captures the whole posting rather than one viewport of it.

The one unavoidable seam: the name in the salutation is in the tracked
`letter.yaml`, because the letter cannot be rendered without it. Everything
past that name is in the dossier.

### Your signature

```yaml
# data/private.yaml
signature: "assets/private/signature.png"
```

`assets/private/` is gitignored, and the only file that names the path is
`data/private.yaml`, which is gitignored too — so no tracked file mentions it
even by name. A transparent PNG around 800px wide, scanned from a black pen,
works best.

If the file is missing, or the key is absent, or there is no `private.yaml` at
all, the letter still builds: it prints the typed name with blank space above
it, which is exactly what you want if you intend to print and sign it. A
scanned signature carries no extra legal weight on an emailed PDF anyway.

### The address block

The CV stores your address as one flat string (`contacts.location`). DIN 5008
needs the parts separately — the recipient block puts them on their own lines,
and the return line joins them with a middle dot. So `private.yaml` carries a
structured version alongside the flat one:

```yaml
address:
  street: "Musterstraße 1"
  postal_code: "76131"     # quoted; "01067" would lose its leading zero
  city: "Karlsruhe"
  country: null            # printed only for a recipient abroad
```

Deriving this by splitting the flat string on commas would work right up until
an address contains one.

> The `city` here is also in the public CV as `Karlsruhe, DE`. `check-clean`
> knows that: a value the committed `data/cv-*.yaml` already contain cannot be
> a leak, so it is dropped from the scan. Without that rule, `export` would
> find "Karlsruhe" in the public site data and refuse to publish the website.

### The layout

DIN 5008 **Form B**, wearing the CV's typeface, accent colour and contact row.
The parts that are not negotiable, because a window envelope and a document
scanner both assume them, are in `templates/letter/theme.typ`:

| Key | | |
|---|---|---|
| `address.top` | `45mm` | Top of the address field, from the paper's edge |
| `body.top` | `98.46mm` | Where the subject line starts |
| `fold.first` / `.second` | `87mm` / `192mm` | Fold marks, at the thirds |
| `fold.punch` | `148.5mm` | Hole-punch mark |

**Those positions are measured from the paper, not from the flow.** The
letterhead and the address field are both `place`d absolutely and consume no
flow height, so neither can push the other down — fold the sheet in thirds and
the address lands in the window whatever the letterhead did.

The consequence is that **the letterhead must fit** in the 33 mm above the
address field; it will not make room for itself. The name, tagline and *one*
contact row fit. A contact row that wraps to two lines does not. That is what
`sender_contacts` is for:

```yaml
sender_contacts: [email, phone, github, website]
```

`location` is left out by default on purpose — your postal address is already
on the page, in the return line above the recipient.

`cvforge letter` prints the page count and warns if it is not 1. A two-page
cover letter is a content problem; cut a paragraph.

### The letter YAML

```yaml
meta:
  lang: de              # picks the CV the sender identity is read from
  slug: 2026-09-acme-rendering-engineer   # must match the directory
  date: null            # null = the day you build it

recipient:
  company: "ACME GmbH"
  department: "Personalabteilung"   # optional
  person: "Frau Anna Beispiel"      # optional; printed in the address field
  salutation: "Sehr geehrte Frau Beispiel,"   # optional; see below
  street: "Musterallee 7"
  postal_code: "10115"
  city: "Berlin"
  country: null

job:
  title: "Rendering Engineer"
  reference: "REQ-2026-114"   # optional; info block + subject line
  source: "Ihre Anzeige auf StepStone vom 04.09.2026"   # optional; info block
  url: "https://..."          # optional; recorded, never printed

subject: null                 # optional override of the composed line
sender_contacts: [email, phone, github, website]   # optional; omit for all

body:                         # folded (>) paragraphs, in order
  - >
    …

closing: null                 # optional override
enclosures: ["Lebenslauf", "Zeugnisse"]   # optional
```

**`salutation` is free text on purpose.** German forms of address need a gender
that the data does not carry and should not be guessing, so a named salutation
is written out by hand. Leave it out and you get *Sehr geehrte Damen und
Herren,*.

The subject composes to *Bewerbung als Rendering Engineer – Kennziffer
REQ-2026-114* and prints without the word "Betreff", which DIN 5008 dropped.

Letter strings — the subject prefix, the generic salutation, the closing, the
filenames — live in `LETTER_LABELS` in
[src/cvforge/i18n.py](src/cvforge/i18n.py), a separate table from the CV's.
They have to be: the CV's labels are copied into every published artifact, and
a letter's vocabulary has no business on the website.

---

## Project layout

```
data/            The CV content. This is the source of truth.
applications/    One directory per application; the cover letters.
schema/          JSON Schema for both; wired into VS Code.
src/cvforge/     resolve (YAML -> JSON), letter, dates, i18n, the CLI.
templates/pdf/   The Typst CV renderer.
  theme.typ        All design tokens. No magic numbers live anywhere else.
  template.typ     Page geometry and the set/show rules.
  components/      header, contact row, chips, timeline.
  sections/        One module per CV section.
  main.typ         Document assembly only.
templates/letter/  The Typst letter renderer. Imports ../pdf/ for the theme,
                   the icons and the contact row, so the two documents cannot
                   drift apart on typeface or colour.
assets/          Avatar and the committed fonts.
build/  out/     Generated. Both gitignored.
```

Presentation for the web lives in the **website** repo, not here: a Hugo
partial and a small stylesheet that can use the site's own theme classes. This
repo owns the content; Portfolio owns how it looks. See
[Publishing to the website](#publishing-to-the-website).

---

## Styling the PDF

Almost everything is in [templates/pdf/theme.typ](templates/pdf/theme.typ) —
colours, fonts, spacing, timeline geometry. Change a value there, and the
Tinymist preview updates as you type.

A handful of constants are load-bearing and commented as such in the source.
The ones worth knowing before you touch the timeline:

- The rail is **one `grid.vline` spanning the whole grid**, not a segment per
  entry. That is what makes it survive a page break cleanly.
- `timeline.date-pad` keeps the node circle — which sits on the column
  boundary — off the date text.
- `timeline.node-dy` aligns the circle to the first baseline of the title. It
  is calibrated against `timeline.title-size`; retune it if you change that.
- `chip.outset` grows the chip background without affecting layout, so a line
  of chips keeps the same height as a line of plain text.
- The contact row **packs its own lines** rather than letting Typst wrap it.
  To the line breaker a `|` separator is just more inline content, so a wrapped
  row kept whichever one landed at the end of the line — a divider dividing
  nothing. `contact-row` measures the items and decides the breaks itself, so a
  separator is only drawn between two items that really are side by side.

### The two-column layout

The body is a two-column grid: the timeline sections on the left, a narrow
aside on the right carrying Skills and Languages. Which section goes where is
decided in [templates/pdf/main.typ](templates/pdf/main.typ) by two lists,
`MAIN-SECTIONS` and `ASIDE-SECTIONS` — move a name between them to move the
section.

The geometry is in `theme.sidebar`. Two things about it are worth knowing:

- **The sidebar is narrow on purpose, and one chip per row is what allows it.**
  Chips wrapping inline need roughly 45 mm; stacked they fit in 28 mm. That
  matters more than it sounds: the main column holds the tall content, so every
  millimetre the sidebar takes costs *more* height than it saves. Widening the
  sidebar back to 45 mm pushes the CV onto a second page.
- **`header.photo-size` is independent of `sidebar.width`.** The photo is
  28 mm and the sidebar column 32 mm, so the photo sits roughly above the
  column, but they are separate keys — change one and the other stays put.
- **`sidebar.gutter` and `sidebar.pad` must stay equal.** The rule is drawn at
  the start of the sidebar column, so `gutter` is the air to its left and `pad`
  the air to its right. They were one value once, which put 6 mm on the main
  side and 0.2 mm on the sidebar side — the rule read as a border stuck to the
  content rather than a divider between two columns.

Note that `sidebar.width` is the **whole column**; the usable content width is
`width - pad`. Keep that at 28 mm when retuning — it is what lets the widest
chips (`ONNX Runtime`, `GitLab CI/CD`) sit on one line.

The aside starts below the header, so it lines up with the first section
heading whether or not there is a photo. Nothing special-cases the two cases.

### The projects page

`meta.projects_layout: page` puts projects on their own page after the CV. It
has no sidebar, so the full width is available: each entry keeps the same
timeline rail as the CV, with the title, repository link, description and chips
on the left and a screenshot on the right.

**Sizing the image column against the text.** Two keys, both in
[templates/pdf/theme.typ](templates/pdf/theme.typ):

| Key | |
|---|---|
| `projects.image-width` | Width of the image column. Currently `62mm`. |
| `timeline.aside-gap` | Space between the text and the image. Currently `6mm`. |

The text column is whatever is left — it is a `1fr`, so it absorbs the
remainder and you never set it directly. On A4 with the current margins the
arithmetic is:

```
176mm page content
 - 17.4mm  timeline dates (theme.timeline.date-col, 5.2em)
 -  5.0mm  rail gutter    (theme.timeline.gutter, 1.5em)
 - 62.0mm  image          (theme.projects.image-width)
 -  6.0mm  gap            (theme.timeline.aside-gap)
 = 85.6mm  text
```

So widening the image by 10mm narrows the text by the same 10mm. Images are
top-and-bottom centred against their entry, and drawn without a frame
(`projects.image-stroke`).

An entry with no `image` still reserves the column, so every entry's text has
the same width and the page reads as one list rather than a ragged one.

Images live in `assets/projects/`; `cvforge check` warns if a path does not
resolve, because a missing image is a hard Typst error rather than a blank
space. Use `url_note` for a project whose code is not public yet — it prints in
italics where the repository link would go.

A single-year entry (`start` and `end` the same) prints the year once rather
than stacking it twice, and is nudged down by `theme.timeline.single-date-dy`
so it centres on its node — the date is 8pt against a 10pt title, so without
that it rides visibly high. Both apply everywhere, not just here.

The running footer numbers pages from page 2 onward, so the projects page shows
`2 / 2` and the CV page stays clean. If you would rather have `1 / 2` on the
first page too, change `counter(page).get()` to `counter(page).final()` in
[templates/pdf/template.typ](templates/pdf/template.typ).

### Fitting on one page

With `projects_layout: omit` both CVs fit on one page; with `page` they are
two, the second being the projects page. `cvforge pdf` prints the count so a
regression is visible immediately:

```
wrote out/cv-de.pdf  (1 page)
```

**Check German first.** German prose runs longer than English, so `cv-de.yaml`
is the tighter of the two and will spill first. If it does, the effective knobs
are `timeline.row-gutter`, `h1.above`, `leading` and `size` — in that order.

Do **not** shrink `timeline.date-col` to buy width; at 4.5em, "Mar 2026" and
"May 2025" wrap onto two lines. The sidebar width is the place to reclaim
space.

If the CV does overflow, the sidebar's vertical rule continues onto page two as
a short stub. That is a symptom of the overflow, not a separate bug — fix the
overflow.

### Level bars and notes

A skill item or a language may carry an optional `rating` from 1 to 5. It
renders as a short bar beside the name instead of a chip, and the bar is a
fixed width so the filled fraction is comparable between rows.

```yaml
skills:
  - group: "Programming"
    items:
      - { name: "C++", rating: 5, note: "professional" }
      - { name: "Rust", rating: 2, note: "personal projects" }
      - "Slang"          # neither -> ordinary chip

languages:
  - name: "German"
    level: "native" # the note, in this section's own language
    rating: 5
```

`note` is usually the more valuable of the two: a bar says *how much*, a note
says *in what context*, and "professional" versus "personal projects" is the
thing a reader is actually scanning for. A rated skill and a spoken language
are the same shape — name, optional bar, muted line — and share one component,
[components/bars.typ](templates/pdf/components/bars.typ).

**Use it sparingly.** A bar against every skill turns into wallpaper, and it
invites the reader to ask what the missing two fifths are — which is a question
you gain nothing by raising. It earns its place where the words are genuinely
vague: spoken languages, and the one or two languages you write daily.

Geometry lives in `theme.bar`. Rated rows are padded by `chip.inset.y` so they
occupy the same vertical space as a chip and the group keeps its rhythm.

### `interests`

Optional, sidebar only, rendered as plain chips.

```yaml
interests: ["Weight Lifting", "Hiking", "PC Modding", "Spaceflight"]
```

Keep these **non-technical**. Rendering, graphics and AI are already the
tagline, the profile, the skills and every project — listing them again spends
lines proving a point the CV has made four times over. The value of this
section is the part the rest of the CV cannot show.

### Chip layout in the sidebar

`theme.sidebar.chip-layout` takes two values:

| | |
|---|---|
| `wrapped` *(default)* | As many chips per row as fit. |
| `stacked` | One chip per row. |

`wrapped` is never taller than `stacked` for the same content — the wrapped
run's line spacing is set to `chip-gap`, so it only ever saves rows. With the
current data it saves about 17mm, which is what makes room for the interests
section: `stacked` ends at 280mm against a 281mm content area.

`stacked` is what the 28mm column was originally sized for and gives a cleaner
right edge, so it is worth trying if you trim the skills list.

### Building without a photo

Some employers ask for a CV without a photograph. Set `photo` to null in the
data file and rebuild:

```yaml
meta:
  photo: null # was "assets/avatar.jpg"
```

The header collapses to full width, the aside still starts level with the
`PROFILE` heading. Remember to
revert it afterwards.

---

## Publishing to the website

The CV sections on [dom-wuest.de/about/](https://dom-wuest.de/about/) are
rendered by the [Portfolio](https://github.com/dom-wuest/Portfolio) repo from
data exported out of here. One command writes everything it needs:

```bash
uv run cvforge export --to ../Website/Portfolio
```

It resolves both languages as **public** — not overridable, because this writes
into a public repository — copies the resolved artifacts to `data/cv/{en,de}.json`,
compiles public-profile PDFs into `static/files/`, and runs `check-clean` over
exactly those files before declaring success. It refuses to run at all unless
the target contains `config/_default/hugo.yaml`, so a mistyped path fails loudly
instead of scattering files somewhere unexpected.

The public PDFs go straight to the website and never touch `out/`, so the
full-profile PDF you send with applications is not silently replaced.

### When you change the CV

```bash
uv run cvforge check                          # validate
uv run cvforge export --to ../Website/Portfolio
```

Then commit both repos and **cut a release in the website repo** — it deploys on
`release: published`, not on push.

### When you change how the CV looks on the site

Edit `layouts/partials/cv.html` or `assets/css/custom.css` in Portfolio. Nothing
here changes and nothing needs re-exporting. That split is the point: content in
this repo, presentation in that one.

### Why a file copy rather than automation

CVForge is private. Anything that *pulls* — a submodule, a CI fetch — needs a
token in the public repo's secrets, breaks for pull requests from forks, and
makes a public build depend on a private repo staying reachable. A local copy
needs none of that, and since the site only deploys on a published release,
automating the copy would not save a step anyway.

---

## Troubleshooting

**Icons are blank, or `unknown font family: font awesome 7 free solid`**
The compile is missing `--font-path assets/fonts`. The `cvforge` CLI always
passes it; if you are calling `typst` by hand, add it. In VS Code, check
`tinymist.fontPaths` in `.vscode/settings.json`.
To compile without the fonts entirely, set `FALLBACK` to `true` in
[templates/pdf/icons.typ](templates/pdf/icons.typ) — it draws stub circles.

**`error: file not found (searched at /build/cv-en.json)`**
Either the resolve step has not run (`uv run cvforge resolve --lang en`), or
Typst was invoked without `--root .`.

**`cv-en.yaml failed validation: at $.languages[0].level: False is not of type 'string'`**
YAML turned a bare `no` into a boolean. Quote it: `level: "no"`. The
`$.…` part is the exact path to the offending node.

**The PDF typeface looks wrong**
Typst fell back silently because it could not find Inter — again a missing
`--font-path`.

**`typst not found on PATH`**
Install it, or restart the terminal after installing so the PATH refreshes.

---

## Licence

Code and templates: see [LICENSE](LICENSE). The bundled fonts are SIL OFL 1.1;
their licences are in [assets/fonts/](assets/fonts/). The CV content itself is
personal data, not licensed for reuse.
