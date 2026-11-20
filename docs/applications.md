# Applications

[← README](../README.md) · [Getting started](getting-started.md) · [CV](cv.md) · [Private data](private-data.md) · [Cover letters](cover-letters.md) · **Applications** · [Tracking](tracking.md) · [Website](website.md) · [Claude](with-claude.md) · [Commands](commands.md)

---

A CV is written once and reused. An application is the opposite: one company,
one posting, one time. CVForge keeps each in a folder of its own and builds
from it a send-ready set of documents - the letter, the matching CV and every
attachment, numbered and named the way an upload form expects.

- [Creating one](#creating-one)
- [A CV tailored to one application](#a-cv-tailored-to-one-application)
- [The send-ready folder](#the-send-ready-folder)
- [Once it is sent](#once-it-is-sent)
- [With Claude](#with-claude)

## Creating one

```bash
uv run cvforge new 2026-09-acme-rendering-engineer --lang de
```

```
<home>/applications/2026-09-acme-rendering-engineer/
  letter.yaml     the letter itself - see cover-letters.md
  cv.yaml         a tailored CV - only with `new --cv`
  dossier.yaml    the posting, the people, the timeline - see tracking.md
  posting/        the archived posting
  attachments/    one-off files for this job
  recv/           documents they sent you - forms, questionnaires (create it when needed)
  send/           what `apply` built (created by apply)
```

Date-prefix the slug and the folders sort themselves chronologically.
`--from <slug>` starts the letter and the tailored CV from an earlier
application instead of the blank scaffold; `cvforge list --match` finds the
right one (see [tracking.md](tracking.md#finding-similar-applications)).

None of it is in the repository - it lives in your
[home](private-data.md#the-home). Archive the posting as a **PDF print, not a
screenshot**: the text stays selectable and you get the whole posting, not one
viewport of it.

Fill in `letter.yaml` ([cover-letters.md](cover-letters.md)), then:

```bash
uv run cvforge check                                   # validates the letter and dossier too
uv run cvforge letter 2026-09-acme-rendering-engineer  # the draft, to look at
uv run cvforge apply  2026-09-acme-rendering-engineer  # the folder to send
```

## A CV tailored to one application

```bash
uv run cvforge new 2026-09-acme-rendering-engineer --lang en --cv
```

copies `data/cv-en.yaml` to `applications/<slug>/cv.yaml`. Edit the copy -
reword the profile, add relevant coursework, reorder skills, drop the photo.
While it exists, `letter`, `apply` and `check` use it instead of the base CV,
for the attached CV and the letterhead alike. `private.yaml` is merged into it
exactly as into the base CV.

The base CV is never touched, which matters because it also feeds the
website: `export` only ever reads `data/cv-*.yaml`. The copy is a snapshot, so
later edits to the base CV do not reach an application already sent.

## The send-ready folder

`apply` writes a folder numbered in the order an employer expects, named the
way an upload form expects:

```
<home>/applications/2026-09-acme-rendering-engineer/send/
  01_Dominik_Wuest_Anschreiben.pdf
  02_Dominik_Wuest_Lebenslauf.pdf
  03_Dominik_Wuest_Masterzeugnis.pdf
  04_Dominik_Wuest_Arbeitszeugnis_Fraunhofer_IOSB.pdf
```

(`_Cover_Letter` / `_CV` for `lang: en`.) The CV is rebuilt fresh so the
documents are the same vintage, and the folder is emptied first so a dropped
attachment cannot linger. If an attachment file is missing, `apply` refuses and
names it rather than produce an incomplete application - and leaves the
previous folder as it was.

`apply` ends with one line to read before sending:

```
summary: letter 1 page | cv 2 pages (expected 2) | cv source data/cv-de.yaml | 2 attachments
```

and warns if the letter is over a page, or the CV has more pages than its
`projects_layout` allows - which means it overflowed.

## Once it is sent

Once the dossier records the application as sent (`applied:` set, or a status
past `draft`), `apply` refuses to touch `send/` again: from then on it holds
what the employer actually received, not what the sources would produce today.
`apply --force` rebuilds it anyway; `cvforge letter` still builds a draft to
look at, outside `send/`.

What happens next - calls, interviews, answers - goes into the dossier:
[tracking.md](tracking.md).

## With Claude

Two ways to let Claude do the typing, both described in [with-claude.md](with-claude.md):

- **Claude Desktop** - a local MCP server lets Claude read your past
  applications, draft the new one with you, and build it in the same chat.
- **Claude Code** - `/new-application` with a brief from a letter-writing chat
  scaffolds the application, fills it in, tailors the CV copy, runs `apply`
  and reports page counts and anything that needs you.
