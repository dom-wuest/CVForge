# CVForge

One CV, written once as data. From that single source:

- **A4 PDF** for job applications, typeset with [Typst](https://typst.app)
- **The website** — the public CV data and PDFs, exported into the
  [Portfolio](https://github.com/dom-wuest/Portfolio) repo for dom-wuest.de/about/
- **Complete applications** — a cover letter, the matching CV and every
  attachment, built into one send-ready folder per job

In German and English. Your phone number, street address, signature and
certificates live in gitignored files and never reach a tracked file or the
website — by construction, not by discipline.

> Working on the code or the templates rather than the content? Read
> [CLAUDE.md](CLAUDE.md) — architecture, conventions, the private-data
> guarantees, every design decision and the verification recipe live there.

---

## Contents

- [Quick start](#quick-start)
- [Commands](#commands)
- [Which file to edit](#which-file-to-edit)
- [Private data](#private-data)
- [The CV YAML format](#the-cv-yaml-format)
- [Applications and cover letters](#applications-and-cover-letters)
- [Previewing while you write](#previewing-while-you-write)
- [Publishing to the website](#publishing-to-the-website)
- [Troubleshooting](#troubleshooting)
- [Licence](#licence)

---

## Quick start

Two tools. Both are single binaries.

| Tool | What for | Install |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python environment and the `cvforge` CLI | `winget install astral-sh.uv` · `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [typst](https://github.com/typst/typst) | Typesets the PDFs | `winget install Typst.Typst` · `cargo install --locked typst-cli` |

Fonts are committed to the repo, so there is nothing to install and the output
is identical on every machine.

```bash
uv run cvforge pdf --lang en      # -> out/cv-en.pdf
```

That is the whole setup. `uv` creates the virtualenv on first run, and the
first Typst compile downloads the `fontawesome` package once.

---

## Commands

Everything goes through one CLI. In VS Code the same commands are under
**Tasks: Run Task**.

| Command | Does |
|---|---|
| `uv run cvforge pdf --lang en` | Build `out/cv-en.pdf` (`--lang de` for German) |
| `uv run cvforge all` | The CV for every language |
| `uv run cvforge check` | Validate all data files, report content warnings |
| `uv run cvforge new <slug> --lang de` | Scaffold a new application |
| `uv run cvforge letter <slug>` | Build just that cover letter → `out/letters/<slug>.pdf` |
| `uv run cvforge apply <slug>` | Build the send-ready folder: letter, CV, attachments |
| `uv run cvforge dev --lang en` | Live-preview loop for the CV — see [Previewing](#previewing-while-you-write) |
| `uv run cvforge dev --letter <slug>` | Live-preview loop for a letter |
| `uv run cvforge export --to <site>` | Publish the public CV to the website repo |

---

## Which file to edit

| You want to change | Edit | Tracked? |
|---|---|---|
| CV content — experience, education, skills, projects | `data/cv-en.yaml`, `data/cv-de.yaml` | yes |
| Phone number, street address, signature, which certificates exist | `data/private.yaml` | **no** |
| A cover letter for one application | `applications/<slug>/letter.yaml` | yes |
| Notes on that application — the posting, who you spoke to, status | `applications/<slug>/dossier.yaml` | **no** |
| The scanned certificates themselves | `assets/private/documents/` | **no** |
| Your signature scan | `assets/private/signature.png` | **no** |
| How the PDFs look | `templates/` — see [CLAUDE.md](CLAUDE.md) | yes |

The two languages are independent files with identical structure. Nothing
forces them to agree; keep them in step by hand.

---

## Private data

A CV for an application needs a phone number and a street address. A public
repo and a public website must not have them. So the committed
`data/cv-<lang>.yaml` holds only placeholders, and the real values live in one
gitignored file:

```bash
cp data/private.example.yaml data/private.yaml
```

```yaml
contacts:                # keyed by the contact's `id` in cv-<lang>.yaml
  phone:
    value: "+49 721 1234567"
    url: "tel:+491234567"
  location:
    value: "Musterstraße 1, 76131 Karlsruhe"

address:                 # the same address, split up for the letter
  street: "Musterstraße 1"
  postal_code: "76131"   # quoted, or "01067" loses its zero
  city: "Karlsruhe"
  country: null

signature: "assets/private/signature.png"

documents:               # certificates you attach — see Attachments below
  - id: masterzeugnis
    file: "assets/private/documents/masterzeugnis.pdf"
    label: "Masterzeugnis"
```

`private.example.yaml` documents every key. Everything is optional: with no
`private.yaml` at all, the CV builds with placeholders and the letter with a
typed name, and the build tells you so.

A contact in `cv-<lang>.yaml` says which kind of private it is. `private:
hidden` (the phone) vanishes from the website entirely; `private: refine` (the
location) is published as `Karlsruhe, DE` and only sharpened to the full
address for applications.

**The guarantee.** `export` builds the website's copy with `private.yaml`
ignored, checks the artifact says so, and greps everything it wrote for every
value in `private.yaml` before it finishes. If anything matches, nothing is
published. You do not have to remember any of this — it is not optional. How
each layer works is in [CLAUDE.md](CLAUDE.md).

---

## The CV YAML format

`schema/cv.schema.json` enforces all of it, and VS Code shows completions and
errors as you type (with the `redhat.vscode-yaml` extension, which the folder
recommends).

### Three rules that bite

**1. Dates are quoted strings**, `"YYYY"` or `"YYYY-MM"`. Precision follows
the length: `"2021-10"` renders as *Oct 2021*, `"2023"` as *2023*. Unquoted,
YAML turns a full `2021-10-01` into a date object, and the two look identical
in a diff. `end: null`, or no `end`, means ongoing → *Present* / *heute*.

**2. Quote anything YAML coerces.** `no`, `on`, `off`, `yes` become booleans.
`grade: 1.20` becomes the float `1.2`. Always `grade: "1.2"`.

**3. Store data, not presentation.**

```yaml
grade: "1.2"           # yes
grade_note: current

meta: "Current Grade 1.2"   # no
```

The renderers compose the display string. This is what lets the website show
the same facts in a different shape.

Entry order in the file is display order. Prose uses `>` (folded); reserve
`|` (literal) for text that needs real line breaks. `cvforge check` catches
all three mistakes.

### `meta`

```yaml
meta:
  lang: en                                  # must match the filename
  name: "Dominik Wüst"
  tagline: "M.Sc. Computer Science – …"
  photo: "assets/avatar.jpg"                # repo-relative; null for none
  projects_layout: page                     # inline | page | omit
```

Some employers ask for a CV without a photograph: set `photo: null`, rebuild,
revert. The header collapses to full width and nothing else moves.

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
    value: "github.com/dom-wuest"
    url: "https://github.com/dom-wuest"
```

| Key | |
|---|---|
| `id` | Required. Lowercase kebab-case. |
| `icon` | Required. Font Awesome icon name. |
| `value` | Required. The displayed text. |
| `url` | Optional. Makes it a link. |
| `brand` | `true` for `github`, `linkedin`, … (the Brands font has no solid variant). |
| `private` | `hidden` or `refine` — see [Private data](#private-data). |

**Write profile links as `linkedin.com/in/handle`, not just `handle`.** The
icon tells a human which platform it is, but the bare handle is not typeable
from a printed page, and ATS URL extraction matches on the domain. Drop the
`https://www.` — it is noise. Keep the full URL in `url` so the PDF stays
clickable.

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

To add an entry: copy an existing one, put it where it should appear (newest
first), give it a unique lowercase `id`, quote the dates, write one achievement
per highlight, then `uv run cvforge check`. Do the same in the other language.

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
    grade_note: current                # current | preliminary | final | null
    tags: ["Computer Graphics"]
```

`thesis`, `specialization`, `minor` and `grade` are composed into one meta line
with ` – ` separators, skipping whatever is absent. `grade_note: current`
renders *Current Grade 1.2* (studies still running), `preliminary` renders
*Preliminary Grade 1.2* (degree obtained, final grade not yet published), and
`final` renders *Grade 1.2*.

### `projects` *(optional)*

Where projects appear is a single switch, `meta.projects_layout`:

| | |
|---|---|
| `inline` *(default)* | In the main column with the other sections, as an ordinary timeline. |
| `page` | On its own full-width page after the CV, with room for a screenshot beside each entry. |
| `omit` | Left out entirely. |

It is `omit`, **not** `off` — YAML 1.1 reads an unquoted `off` as `false`.
`image` is only read by the `page` layout.

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

Images live in `assets/projects/`; `cvforge check` warns if one is missing,
because a missing image is a hard Typst error.

### `skills`

A **list of groups**, not a mapping — mappings do not guarantee order, and
order is meaningful here.

```yaml
skills:
  - group: "Programming"
    items:
      - { name: "C++", rating: 5, note: "professional" }
      - { name: "Rust", rating: 2, note: "personal projects" }
  - group: "Graphics & GPU"
    items: ["Vulkan", "Slang", "GLSL", "CUDA"]   # bare names -> chips
```

An item is either a **bare name**, rendered as a chip, or a **mapping** with an
optional `rating` (1–5, draws a bar) and an optional `note` (a short muted line
beneath). Either promotes the item onto a full-width row of its own.

**Use ratings sparingly.** A bar against every skill turns into wallpaper, and
it invites the reader to ask what the missing two fifths are — a question you
gain nothing by raising. `note` is usually the more valuable of the two: a bar
says *how much*, a note says *in what context*.

Skills render directly above the spoken `languages` section, so **do not name
a group after it** — in German the two would be the identical word *Sprachen*.
Use *Programming* / *Programmierung*.

### `languages`

`level` is free text, already in the file's own language.

```yaml
languages:
  - name: "German"
    level: "native"
    rating: 5 # optional, 1-5
```

### `interests` *(optional)*

```yaml
interests: ["Weight Lifting", "Hiking", "PC Modding", "Spaceflight"]
```

Keep these **non-technical**. Rendering and AI are already the tagline, the
profile, the skills and every project. The value of this section is the part
the rest of the CV cannot show.

---

## Applications and cover letters

A CV is written once and reused. A cover letter is the opposite: one company,
one posting, one time. Each application is a directory:

```bash
uv run cvforge new 2026-09-acme-rendering-engineer --lang de
```

```
applications/2026-09-acme-rendering-engineer/
  letter.yaml     the letter itself             TRACKED
  dossier.yaml    the posting, the people       gitignored
  posting/        the archived posting          gitignored
  attachments/    one-off files for this job    gitignored
```

Date-prefix the slug and the directory sorts itself chronologically.

The letter YAML holds only what is specific to this application. Your name,
tagline, contacts, address and signature come from the CV and `private.yaml`,
so the letterhead can never disagree with the CV stapled behind it.

Fill in `letter.yaml`, then:

```bash
uv run cvforge check                                   # validates it too
uv run cvforge letter 2026-09-acme-rendering-engineer  # the draft, to look at
uv run cvforge apply  2026-09-acme-rendering-engineer  # the folder to send
```

`apply` writes a folder numbered in the order an employer expects, named the
way an upload form expects:

```
out/applications/2026-09-acme-rendering-engineer/
  01_Dominik_Wuest_Anschreiben.pdf
  02_Dominik_Wuest_Lebenslauf.pdf
  03_Dominik_Wuest_Masterzeugnis.pdf
  04_Dominik_Wuest_Arbeitszeugnis_Fraunhofer_IOSB.pdf
```

(`_Cover_Letter` / `_CV` for `lang: en`.) The CV is rebuilt fresh so the
documents are the same vintage, and the folder is emptied first so a dropped
attachment cannot linger. If an attachment file is missing, `apply` refuses and
names it rather than produce an incomplete application.

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
  country: null                     # only for a recipient abroad

job:
  title: "Rendering Engineer"
  reference: "REQ-2026-114"         # optional; info block + subject line
  reference_label: "Referenznummer" # optional; whatever THIS posting calls it
  source: "Ihre Anzeige auf StepStone vom 04.09.2026"   # optional; info block
  url: "https://..."                # optional; recorded, never printed

subject: null                       # optional override of the composed line
sender_contacts: [email, phone, github, website]   # optional; omit for all

body:                               # folded (>) paragraphs, in order
  - >
    …

attachments:                        # optional; see Attachments
  - masterzeugnis
closing: null                       # optional override
enclosures: null                    # optional; derived from attachments when unset
```

**`salutation` is free text on purpose.** German forms of address need a gender
the data does not carry and should not guess, so a named salutation is written
out by hand. Leave it out for *Sehr geehrte Damen und Herren,*.

**`reference_label`** — every career portal has its own word for the same
number: *Kennziffer*, *Referenznummer*, *Job-ID*, *Role ID*. Copy the posting's
own wording; quoting it back is the whole reason to print the number. Omit it
for *Kennziffer* / *Reference*.

**`sender_contacts`** — the letterhead has to fit above the address field, and
one contact row does while two do not. `location` is left out by default
because your postal address is already on the page, in the return line above
the recipient. If `cvforge letter` warns that the letter is two pages, trim
here or cut a paragraph.

### What is tracked and what is not

`letter.yaml` is committed: it is your own writing, and a company's postal
address is public imprint data. `dossier.yaml`, `posting/` and `attachments/`
are not: a recruiter's name and phone are someone else's personal data, and an
archived posting is someone else's copyrighted text. Nothing renders from the
dossier — it exists so that three weeks later, when the posting is gone and
you are in the interview, the facts are still somewhere.

Archive the posting as a **PDF print, not a screenshot**: the text stays
selectable and you get the whole posting, not one viewport of it.

### Your signature

```yaml
# data/private.yaml
signature: "assets/private/signature.png"
```

A transparent PNG around 800px wide, scanned from a black pen, works best. If
the file is missing, the letter prints the typed name with blank space above
it — which is what you want if you intend to print and sign. A scanned
signature carries no extra legal weight on an emailed PDF anyway.

### Attachments

Certificates, transcripts and references are the same files for every
application, so they are declared once in `private.yaml` and picked per letter
by id. Put the files in `assets/private/documents/`.

```yaml
# data/private.yaml
documents:
  # One file, one name — issued in German, sent as-is to everyone.
  - id: masterzeugnis
    file: "assets/private/documents/scan_2023_04_11_0003.pdf"
    label: "Masterzeugnis"

  # One file, two names — a bilingual certificate; only the Anlagen line changes.
  - id: bachelorzeugnis
    file: "assets/private/documents/bachelorzeugnis.pdf"
    label:
      de: "Bachelorzeugnis"
      en: "Bachelor's Degree Certificate"

  # Two files, two names — issued separately per language.
  - id: transcript-master
    file:
      de: "assets/private/documents/notenauszug_master_de.pdf"
      en: "assets/private/documents/transcript_master_en.pdf"
    label:
      de: "Notenauszug (laufendes Masterstudium)"
      en: "Transcript of Records (Master, in progress)"
```

```yaml
# applications/<slug>/letter.yaml
attachments:
  - masterzeugnis
  - transcript-master
  - file: "attachments/portfolio.pdf"   # relative to this application
    label: "Arbeitsproben"              # for this job only
```

The name you *send* comes from `label`, not from whatever the scanner called
the file. `file` and `label` each take one string or one per language; a letter
picks the edition matching its own `lang`. If a document has per-language files
but not one for your language, the other is attached and the build says so.

The "Anlagen:" line under your signature derives from this — the CV, then each
attachment's label — so it can never claim a document the folder does not
contain. Set `enclosures:` only to reword it.

Copying preserves digital signatures on the PDFs: the copy is byte-identical,
and a signature covers the file's content, not its name. Merging or
re-compressing would break them; nothing here does that.

---

## Previewing while you write

**Recommended: the [Tinymist](https://marketplace.visualstudio.com/items?itemName=myriad-dreamin.tinymist)
VS Code extension**, which the folder recommends on open. It gives a live
preview that updates as you type, with click-to-jump between source and page.

Two halves, because Tinymist watches Typst files but knows nothing about YAML:

1. **Terminal** — `uv run cvforge dev --lang en`, or
   `uv run cvforge dev --letter <slug>` for a cover letter.
   Regenerates the data on every save.
2. **Editor** — open `templates/pdf/main.typ` (or `templates/letter/main.typ`)
   and run **Tinymist: Preview** from the command palette.

Editing a `.yaml` file regenerates the data, which the preview picks up a
moment later. To preview the German CV, change `lang=en` to `lang=de` in
`tinymist.typstExtraArgs` in `.vscode/settings.json`.

Without Tinymist, add `--compile` to `dev` and keep a PDF viewer open on the
output.

---

## Publishing to the website

```bash
uv run cvforge check
uv run cvforge export --to ../Website/Portfolio
```

Then commit both repos and **cut a release in the website repo** — it deploys
on `release: published`, not on push.

Changing how the CV *looks* on the site is done in the Portfolio repo
(`layouts/partials/cv.html`, `assets/css/custom.css`); nothing here changes
and nothing needs re-exporting.

---

## Troubleshooting

**`cv-en.yaml failed validation: at $.languages[0].level: False is not of type 'string'`**
YAML turned a bare `no` into a boolean. Quote it: `level: "no"`. The `$.…`
part is the exact path to the offending node.

**`typst not found on PATH`**
Install it, or restart the terminal after installing so the PATH refreshes.

Anything else — blank icons, wrong typeface, `file not found (searched at
/build/…)` — is in the [CLAUDE.md troubleshooting section](CLAUDE.md#troubleshooting).

---

## Licence

Code and templates: see [LICENSE](LICENSE). The bundled fonts are SIL OFL 1.1;
their licences are in [assets/fonts/](assets/fonts/). The CV content itself is
personal data, not licensed for reuse.
