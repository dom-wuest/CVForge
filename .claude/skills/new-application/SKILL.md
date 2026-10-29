---
name: new-application
description: Build a complete CVForge job application from a markdown brief written in the claude.ai letter chat - scaffold applications/<slug>/ with `cvforge new`, fill letter.yaml and dossier.yaml, apply confirmed CV changes to a tailored cv.yaml copy, run `cvforge apply`, check the PDFs and report page counts and problems. Use when the user hands over an application brief, cover letter text for a company, or says "create/build an application from this".
argument-hint: <brief.md> <posting.pdf> (or attach both)
allowed-tools: Read, Write, Edit, Glob, Grep, WebSearch, WebFetch, Bash(uv run cvforge:*), Bash(git status:*), Bash(git diff:*), Bash(git check-ignore:*)
---

# /new-application

Turn a brief into a send-ready folder in `<home>/applications/<slug>/send/`,
then report.

**Where things are.** Applications and `private.yaml` live in the user's home
folder, outside the repository. Run `uv run cvforge home` first: it prints the
home. Below, `applications/<slug>/` means `<home>/applications/<slug>/` and
`private.yaml` means `<home>/private.yaml` (without a home: the repository's
`applications/` and `data/private.yaml`). If `cvforge home` reports an error,
stop and show it to the user.

## Inputs

The skill expects two inputs:

1. **The brief** - a markdown file (`<company>-<role>.md`).
2. **The posting** - a PDF of the job advertisement.

Each one counts as given only if it is
- **attached** to the message that invoked the skill (the usual way, from the
  VS Code chat), or
- named by a **path** in the arguments (`$ARGUMENTS`) or the message, and that
  path resolves to an existing file.

Check both before step 1. If either is missing - not attached, no path, or a
path that does not resolve - **stop and ask the user to add it**, naming which
one is missing (and the path you tried, if there was one). Do nothing else
until both are there.

**Never search for an input.** No Glob, Grep, `find` or `ls` to locate one -
not in the repo, not in Downloads, nowhere else on the machine. A file name
mentioned inside the brief (e.g. its `Quelle:` line) is the letter chat's
reference, not a path to look for.

Read before starting, in this directory:
- [field-mapping.md](field-mapping.md) - brief → letter.yaml / dossier.yaml / cv.yaml
- [report-template.md](report-template.md) - the exact shape of the final report
- [brief-format.md](brief-format.md) - what a well-formed brief contains

## Hard rules

- **Never edit anything in `data/`** - `data/cv-*.yaml` feeds the public
  website - **and never edit `private.yaml`.** CV changes go into
  `applications/<slug>/cv.yaml` only.
- **`private.yaml`: read ids and labels under `documents:` only.** Never
  print, quote or summarise any other value from it.
- **Never touch the private folder** (`<home>/private/`, or `assets/private/`).
  A hook blocks it anyway.
- **Never change the letter's wording.** The text was written and approved in the
  letter chat. Copy it verbatim - only whitespace and YAML quoting may differ.
  Typos you notice go into the report, not into the file.
- **Never overwrite an existing application.** If `applications/<slug>/` exists,
  stop and ask.
- **Never commit, stage or push.** Applications are outside git by design.
- Apply only CV changes the brief marks as **confirmed**. Everything optional or
  unconfirmed goes into the report as "not applied".
- Do not invent facts the brief does not give: no made-up reference numbers,
  no `job.source` phrase unless the brief names where the posting was found.
  A missing postal address is the one thing you look up (step 2) - from a
  source you can cite, never from memory, and always reported as looked up.

## Procedure

1. **Read the brief** and extract every field in field-mapping.md. If the
   language, company, job title or letter text is missing, stop and ask.
   Note anything ambiguous for the report rather than guessing.

2. **Look up the address if the brief has none.** A letter addressed to a bare
   company name looks unfinished, so when the brief gives no postal address
   (no recipient address, no HR department, no contact person with an
   address), find the company's office **in the city the job is in**. If the
   company has no office there, use its headquarters.
   - Search with WebSearch, then confirm with WebFetch on the source itself.
   - **Sources, best first:** the company's own imprint / Impressum or contact
     page; an official register (Handelsregister, Unternehmensregister, the
     Bundestag Lobbyregister, Companies House); the posting itself. Directories
     and aggregators (northdata, komo, LinkedIn, job boards) may only
     *corroborate* - an address found only there is not good enough.
   - If the company site blocks fetching (HTTP 403/429), go down the list
     rather than retrying.
   - Take the **legal entity name** from the source for `recipient.company`
     (e.g. "ACME Deutschland GmbH"), and the street spelled as the source has it.
   - Nothing confirmed by a primary or official source → stop and ask the
     user for the address. Do not fall back to a guess.
   - Record what you found for the report: address, source URL, and how
     current the source is.

3. **Choose the slug**: `YYYY-MM-<company>-<role>` - today's year and month,
   lowercase ASCII, hyphens, role shortened to one or two words
   (e.g. `2026-09-acme-rendering`, `2026-10-globex-ml-intern`). Check with Glob
   that `applications/<slug>/` does not exist.

4. **Scaffold**:
   `uv run cvforge new <slug> --lang <en|de>`, adding `--cv` **only** if the
   brief has at least one confirmed CV change.

5. **Fill `applications/<slug>/letter.yaml`** per field-mapping.md. Edit the
   scaffolded file rather than rewriting it, so its comments stay. Replace
   every placeholder: `ACME GmbH`, `Musterallee 7`, `Rendering Engineer`, and
   all three `TODO` paragraphs.

6. **Fill `applications/<slug>/dossier.yaml`** per field-mapping.md, and save
   the brief verbatim as `applications/<slug>/brief.md` (Write the attached or
   read text). Archive the posting PDF in `applications/<slug>/posting/`:
   - Given as a path: copy that file there, keeping its name, and set
     `posting.archive` and `posting.fetched`.
   - Attached without a path: its pages are in the conversation but there is
     no file to copy. Use its text for `posting.notes`, leave
     `posting.archive: null`, and under "Needs your input" ask the user to save
     the PDF into `applications/<slug>/posting/`.

7. **Tailor `applications/<slug>/cv.yaml`** (only if created in step 4). Apply
   each confirmed change as literally as the brief states it, to the entry it
   names. Keep `>` folded blocks for prose. If a change cannot be expressed
   with the fields the CV schema has (`schema/cv.schema.json`), do not invent
   one: report it as not applied, with the reason.

8. **Build**:
   - `uv run cvforge check` - must not error. Warnings about *other*
     applications are not this run's concern; report only the ones that
     mention this slug or its `cv.yaml`.
   - `uv run cvforge apply <slug>` - read the `summary:` line and collect
     every `note:` and `warning:`.
   - On an error, fix it if it is a YAML or field mistake you made, then rebuild.
     If it is anything else (a missing attachment file, a schema rule), stop
     and report it.

9. **If the letter is more than 1 page**, change layout settings only, one at a
   time, rebuilding after each with `uv run cvforge apply <slug>`:
   1. `meta.justify: true`
   2. `meta.layout: compact` - only if the brief says the application goes
      in electronically (portal upload, email). A posted letter keeps `din`,
      which puts the address where a window envelope expects it.
   If it still overflows, stop. Report how many lines over it is and suggest
   which sentences could go - but do not cut them.

10. **If the CV has more pages than expected** (the `summary:` line says
    `(expected N)`), do not shrink it yourself. Report it, naming which of the
    applied CV changes added length.

11. **Look at the PDFs**: Read `applications/<slug>/send/01_*.pdf` and
    `02_*.pdf`. Check:
    - Letter: the letterhead is not crowding the address field, the subject is
      on one line, the info block is readable, the signature is present, no
      text runs off the page.
    - CV: every applied change is visible where intended, there is no
      half-empty page and no stub of the sidebar rule on page 2, and the
      projects page (if any) is intact.

12. **Safety checks** - all must pass, and all go in the report:
    - `git diff --quiet -- data/` exits 0 (the base CV is untouched).
    - With a home: `uv run cvforge home` names a folder outside the
      repository, so the application is not in git at all. Without one:
      `git check-ignore -q applications/<slug>/letter.yaml` exits 0.
    - `git status --short` lists nothing under `applications/`.

13. **Report** using report-template.md, in the user's language. Lead with the
    status line. Keep it to the template; no narrative.
