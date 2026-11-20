# Private data

[← README](../README.md) · [Getting started](getting-started.md) · [CV](cv.md) · **Private data** · [Cover letters](cover-letters.md) · [Applications](applications.md) · [Tracking](tracking.md) · [Website](website.md) · [Claude](with-claude.md) · [Commands](commands.md)

---

A CV for an application needs a phone number and a street address. A public
repository and a public website must not have them. So the committed
`data/cv-<lang>.yaml` holds only placeholders, and the real values live in
files that are never committed - by construction, not by discipline.

- [The home](#the-home)
- [private.yaml](#privateyaml)
- [hidden and refine](#hidden-and-refine)
- [The guarantee](#the-guarantee)
- [What is tracked and what is not](#what-is-tracked-and-what-is-not)

## The home

Everything personal - `private.yaml`, the signature, the certificates, every
application - lives in one folder outside the repository. Put it somewhere
that syncs, and a second machine has it all and nothing is lost with a disk.
Once per machine:

```bash
uv run cvforge home set "C:\Users\<you>\OneDrive\CVForge"   # writes cvforge.local.toml (gitignored)
uv run cvforge home                                         # what is there, what is missing
```

```
<home>/
  private.yaml         start from data/private.example.yaml
  private/             signature.png, documents/
  applications/<slug>/ letter, CV, dossier, posting - and send/, what apply built
  guidance/            instructions and memory for Claude Desktop - see with-claude.md
  dashboard.html       every application on one page - see tracking.md
  schema/              kept current by cvforge, for editor validation
```

`$CVFORGE_HOME` overrides the setting for one shell. With neither, the
repository is the home (`data/private.yaml`, `assets/private/`,
`applications/`, all gitignored) - which is what a fresh clone gets. A home
that is set but missing, say before OneDrive has synced, stops every command
with an error rather than quietly writing into the repository.

| You want to change | Edit |
|---|---|
| Phone number, street address, signature, which certificates exist | `<home>/private.yaml` |
| The scanned certificates themselves | `<home>/private/documents/` |
| Your signature scan | `<home>/private/signature.png` |
| Anything about one application | `<home>/applications/<slug>/` - see [applications.md](applications.md) |

## private.yaml

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

signature: "private/signature.png"   # relative to the home

documents:               # certificates you attach - see cover-letters.md
  - id: masterzeugnis
    file: "private/documents/masterzeugnis.pdf"
    label: "Masterzeugnis"
```

[`data/private.example.yaml`](../data/private.example.yaml) documents every
key. Everything is optional: with no `private.yaml` at all, the CV builds with
placeholders and the letter with a typed name, and the build tells you so.
`address`, `signature` and `documents` are only read by cover letters - see
[cover-letters.md](cover-letters.md).

## hidden and refine

A contact in `cv-<lang>.yaml` says which kind of private it is:

| | On the website | In the PDF you send |
|---|---|---|
| `private: hidden` (the phone) | Left out entirely | The value from `private.yaml` |
| `private: refine` (the location) | The committed value, `Karlsruhe, DE` | Sharpened to the full address |
| neither | The committed value | The committed value |

Which value is used is decided by the *profile* a build runs with: `full`
merges `private.yaml` in (every PDF and letter you build), `public` ignores it
entirely, even when it exists (forced for the website).

## The guarantee

`export` builds the website's copy with `private.yaml` ignored, checks that
the built data says so, and searches everything it wrote for every value in
`private.yaml` before it finishes. If anything matches, nothing is published.
You do not have to remember any of this - it is not optional.

Four layers, each independent of the others:

1. **Nothing personal is in the working copy.** With a home, private data and
   applications live outside the repository; without one, `.gitignore` blocks
   them.
2. **Committed data holds placeholders only.** A broken `.gitignore` still
   leaks nothing.
3. **The public profile is checked on both sides.** `export` refuses to copy
   anything not built as `public`, and the website's own build fails on the
   same condition.
4. **A leak scan.** `cvforge check-clean` searches the generated files for
   every value in `private.yaml`.

The [MCP server for Claude Desktop](with-claude.md#what-leaves-your-machine) runs
the same scan over everything it returns. How each layer works is in
[CLAUDE.md](../CLAUDE.md#the-private-data-guarantee).

## What is tracked and what is not

| | Tracked? |
|---|---|
| `data/cv-en.yaml`, `data/cv-de.yaml` - the CV content | yes |
| `data/private.example.yaml`, `applications/_template/` - examples and the scaffold | yes |
| `templates/`, `src/`, `schema/` | yes |
| `docs/demo/` - invented applications for the screenshots | yes |
| `private.yaml`, `private/` - in the home | **no** |
| `applications/<slug>/` - letters, tailored CVs, dossiers, postings | **no** |
| `build/`, `out/` - may contain merged private values | **no** |

Nothing under `applications/` is committed except the `_template/` scaffold. A
recruiter's name and phone are someone else's personal data, an archived
posting is someone else's copyrighted text, and a letter and tailored CV are
drafts for one employer - none of it belongs in a repository whose CV data
also feeds a public website.
