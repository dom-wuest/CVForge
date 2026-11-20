# Getting started

[← README](../README.md) · **Getting started** · [CV](cv.md) · [Private data](private-data.md) · [Cover letters](cover-letters.md) · [Applications](applications.md) · [Tracking](tracking.md) · [Website](website.md) · [Claude](with-claude.md) · [Commands](commands.md)

---

- [Install](#install)
- [Your first build](#your-first-build)
- [Set up your home](#set-up-your-home)
- [VS Code](#vs-code)
- [Live preview](#live-preview)
- [Where to go next](#where-to-go-next)

## Install

Two tools. Both are single binaries.

| Tool | What for | Install |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python environment and the `cvforge` CLI | `winget install astral-sh.uv` · `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [typst](https://github.com/typst/typst) | Typesets the PDFs | `winget install Typst.Typst` · `cargo install --locked typst-cli` |

Fonts are committed to the repository, so there is nothing else to install
and the output is identical on every machine.

## Your first build

```bash
uv run cvforge pdf --lang en      # -> out/cv-en.pdf
```

That is the whole setup. `uv` creates the virtualenv on first run, and the
first Typst compile downloads the `fontawesome` package once.

Without a `private.yaml` the CV builds with the committed placeholders, and
the build says so in one line. That is the expected state of a fresh clone.

To make the CV yours, edit `data/cv-en.yaml` and `data/cv-de.yaml` - the
format is in [cv.md](cv.md) - and check your work as you go:

```bash
uv run cvforge check              # validates every data file, reports content warnings
uv run cvforge all                # the CV in every language
```

## Set up your home

Your phone number, street address, signature, certificates and every
application live in one folder outside the repository: the *home*. Put it
somewhere that syncs, and a second machine has everything and nothing is lost
with a disk. Once per machine:

```bash
uv run cvforge home set "C:\Users\<you>\OneDrive\CVForge"   # writes cvforge.local.toml (gitignored)
uv run cvforge home                                         # what is there, what is missing
```

Then copy `data/private.example.yaml` to `<home>/private.yaml` and fill it in.
[private-data.md](private-data.md) explains every key and why the split exists.

You can skip this step while you only work on the CV: without a home, the
repository itself is the home, with everything personal in gitignored paths.

## VS Code

Open the folder and accept the recommended extensions:

- **YAML** (`redhat.vscode-yaml`) - completions and errors from the JSON
  Schemas in `schema/` as you type, for the CV, letters and dossiers.
- **Tinymist** (`myriad-dreamin.tinymist`) - the live preview below.

Every command is also under **Tasks: Run Task**.

## Live preview

Tinymist gives a preview that updates as you type, with click-to-jump between
source and page. It watches Typst files but knows nothing about YAML, so there
are two halves:

1. **Terminal** - `uv run cvforge dev --lang en`, or
   `uv run cvforge dev --letter <slug>` for a cover letter.
   Regenerates the data on every save.
2. **Editor** - open `templates/pdf/main.typ` (or `templates/letter/main.typ`)
   and run **Tinymist: Preview** from the command palette.

Editing a `.yaml` file regenerates the data, which the preview picks up a
moment later. To preview the German CV, change `lang=en` to `lang=de` in
`tinymist.typstExtraArgs` in `.vscode/settings.json`.

Without Tinymist, add `--compile` to `dev` and keep a PDF viewer open on the
output.

## Where to go next

| You want to | Read |
|---|---|
| Write and lay out your CV | [cv.md](cv.md) |
| Understand where private data goes | [private-data.md](private-data.md) |
| Write a cover letter | [cover-letters.md](cover-letters.md) |
| Build and send an application | [applications.md](applications.md) |
| Keep track of what happens after | [tracking.md](tracking.md) |
| Publish the CV on a website | [website.md](website.md) |
| Let Claude draft and build applications | [with-claude.md](with-claude.md) |
