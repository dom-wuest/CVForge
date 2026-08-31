# CVForge

One CV, written once as data, rendered to two targets:

- **A4 PDF** for job applications — typeset with [Typst](https://typst.app)
- **HTML fragment + stylesheet** for embedding into dom-wuest.de *(scaffolded, not yet implemented)*

The content lives in `data/cv-<lang>.yaml`. Everything else is a renderer. Your
phone number and street address live in a gitignored file and never reach a
tracked file or the website.

```
data/cv-en.yaml ─┐
data/cv-de.yaml ─┼─→ build/cv-<lang>.json ─┬─→ out/cv-<lang>.pdf
data/private.yaml┘   (the resolved artifact)└─→ out/cv-<lang>.html + out/cv.css
   (gitignored)
```

Both renderers read **only** `build/cv-<lang>.json`. Neither reads YAML, and
neither knows `private.yaml` exists. That is what lets a third target (a
plain-text version, JSON-LD, an ATS-friendly PDF) be added later without
touching the data.

---

## Contents

- [Quick start](#quick-start)
- [Commands](#commands)
- [Editing your CV — the dev loop](#editing-your-cv--the-dev-loop)
- [Private data](#private-data)
- [The YAML format](#the-yaml-format)
- [How to add an experience entry](#how-to-add-an-experience-entry)
- [Project layout](#project-layout)
- [Styling the PDF](#styling-the-pdf)
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
| `uv run cvforge html --lang en` | Resolve (always public), then write `out/cv-en.html` + `out/cv.css` |
| `uv run cvforge resolve --lang en` | Just the data step → `build/cv-en.json` |
| `uv run cvforge dev --lang en` | Watch `data/`, regenerate the JSON on every save |
| `uv run cvforge all` | Every PDF and HTML output, for every language present |
| `uv run cvforge check` | Validate the data, report content warnings |
| `uv run cvforge check-clean` | Fail if a private value reached `build/` or `out/` |

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

### The two profiles

| | `--profile full` (default for `pdf`) | `--profile public` (forced for `html`) |
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
3. `resolve` stamps `meta.profile` into the artifact, and the HTML renderer
   **refuses to run** on anything that is not `public`
4. `uv run cvforge check-clean` greps the generated artifacts for every value
   in `private.yaml`, including a digits-only form of the phone number

**Run `check-clean` before publishing HTML to your website.** Publishing is a
one-way action; this check costs a second.

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
renderer possible at all — the HTML version needs the same facts in a different
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

Delete the whole key to omit the section — the PDF drops it automatically.

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
  - group: "Languages"
    items: ["C++", "Python"]
  - group: "Graphics"
    items: ["Vulkan", "Slang", "GLSL"]
```

### `languages`

`level` is free text, already in the file's own language.

```yaml
languages:
  - name: "German"
    level: "native"
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

## Project layout

```
data/            The CV content. This is the source of truth.
schema/          JSON Schema for the above; wired into VS Code.
src/cvforge/     resolve (YAML -> JSON), dates, i18n, the CLI, the HTML stub.
templates/pdf/   The Typst renderer.
  theme.typ        All design tokens. No magic numbers live anywhere else.
  template.typ     Page geometry and the set/show rules.
  components/      header, contact row, chips, timeline.
  sections/        One module per CV section.
  main.typ         Document assembly only.
templates/web/   The HTML renderer (scaffold).
assets/          Avatar and the committed fonts.
build/  out/     Generated. Both gitignored.
```

The two themes are **independent on purpose**. `templates/pdf/theme.typ` is
tuned for A4; `templates/web/cv.css` is meant to be adapted to the host site.
They only have to cover the same data, not the same values.

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

### Fitting on one page

Both CVs currently fit on one page, and `cvforge pdf` prints the page count so
a regression is visible immediately:

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

### Building without a photo

Some employers ask for a CV without a photograph. Set `photo` to null in the
data file and rebuild:

```yaml
meta:
  photo: null # was "assets/avatar.jpg"
```

The header collapses to full width, the aside still starts level with the
`PROFILE` heading, and the HTML fragment drops the `<img>` too. Remember to
revert it afterwards.

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
