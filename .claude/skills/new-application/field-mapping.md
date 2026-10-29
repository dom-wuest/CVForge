# Brief → YAML

Briefs come from the letter chat, often as a German `Feld | Wert` table followed
by the letter and a CV-changes section. Field names vary; map by meaning.

## letter.yaml

| Brief | Key | Rule |
|---|---|---|
| Sprache / Language | `meta.lang` | `en` or `de`. Set by `cvforge new --lang`; do not edit afterwards. |
| - | `meta.slug` | Set by `cvforge new`. Leave it. |
| - | `meta.date` | `null` (= build day) unless the brief fixes a date. |
| - | `meta.layout` | `din`. Every letter has an address - from the brief or looked up (SKILL.md step 2). Only the overflow step may switch to `compact`, and only for an electronic application. |
| - | `meta.justify` | `false`. Only the overflow step in SKILL.md sets `true`. |
| Firma / Company | `recipient.company` | The legal entity at the address: from the brief, or from the source the address was looked up in ("ACME Deutschland GmbH"). Never descriptions in brackets ("ACME (Robotics, founded 2015, …)"). |
| Abteilung / Team | `recipient.department` | Else `null`. |
| Ansprechpartner | `recipient.person` | Full name with form of address as it should print ("Frau Anna Beispiel"). `–` / none → `null`. |
| Anrede / the letter's first line | `recipient.salutation` | **Only** if it differs from the default: en `Dear Hiring Team,` · de `Sehr geehrte Damen und Herren,`. Keep the trailing comma. |
| Adresse | `recipient.street`, `.postal_code`, `.city`, `.country` | From the brief, else looked up: the office in the job's city, else the headquarters (SKILL.md step 2). Write abbreviations out (`Beispielstr.` → `Beispielstraße`). City in its local form (`Köln`, not `Cologne`, even in an English letter - it is what the post reads). Quote the postcode: `"10115"`. `country` only if the company is abroad from your address, in the letter's language. |
| Stelle / Position | `job.title` | The title as posted, without location suffix. |
| Kennziffer / Job-ID / Req ID | `job.reference` | `–` / none → `null`. |
| the posting's own word for it | `job.reference_label` | "Job-ID", "Referenznummer", … Only with a reference; `null` = Kennziffer / Reference. |
| where the posting was found | `job.source` | A full phrase in the letter's language: "Ihre Anzeige auf StepStone vom 04.09.2026". Only if the brief says where. "Online-Portal" alone is not enough → `null`. |
| Anzeige URL | `job.url` | Recorded, never printed. |
| the letter's subject line | `subject` | Compare with the composed line: en `Application for <title>` · de `Bewerbung als <title>`, plus ` – <label> <reference>` if there is a reference. Identical → `null`. Different (e.g. ` (Berlin)` appended) → the brief's line, verbatim. |
| - | `sender_contacts` | Leave the scaffold's `[email, phone, github, website]`. |
| letter paragraphs | `body` | One list item per paragraph, each a `>` folded block, verbatim. **Exclude** subject, salutation, closing and the typed name - those are composed. |
| Unterlagen / Anlagen | `attachments` | See below. CV and letter are never listed - they are always included. |
| closing line | `closing` | Only if it differs: en `Kind regards` · de `Mit freundlichen Grüßen`. |
| - | `enclosures` | `null` (derived from attachments). |

### Attachments

Read `private.yaml` (in the home) → `documents:` and look only at each entry's `id` and
`label`. A label may be a string or a `{de:, en:}` mapping. Match the brief's
document names to labels by meaning ("Masterzeugnis" ↔ `masterzeugnis`;
"Arbeitszeugnis Fraunhofer" ↔ `az-fraunhofer`). List the ids in the brief's
order. "keine Zeugnisse" / only cover letter + CV → `attachments: []`. A
document the brief asks for that matches no id → stop and ask.

A one-off file supplied with the brief goes to `applications/<slug>/attachments/`
and is listed as `{file: "attachments/<name>", label: "<label>"}`.

### YAML gotchas

- Paragraphs as folded blocks, indented two spaces under `- >`. No trailing
  spaces: they become double spaces in the PDF.
- Quote any scalar containing `: `, `#`, a leading `*`/`&`/`!`, or starting with
  a quote character. Quote postcodes and dates.
- Use the en dash `–` where the brief does. Keep typographic quotes as given.

## dossier.yaml

| Brief | Key |
|---|---|
| Kurzbeschreibung, else the Stelle section condensed | `summary` - one or two sentences: domain, problem, stack. What makes this job *this* job; it is what the next similar posting is matched against. |
| Schlagworte, else derived from the posting | `keywords` - 5–10, lowercase English, singular: `[robotics, bin picking, python, ros, edge deployment]`. Reuse words earlier dossiers use (`uv run cvforge list` shows them). |
| Unternehmen section | `company.about` (2–3 sentences). `company.name` only if the usual name differs from the legal entity in `recipient.company` ("ACME Robotics Lab Berlin"). |
| Arbeitsort / Standort | `role.location`, `role.work_model` (`onsite`/`hybrid`/`remote`, else `null`), `role.employment` (`full-time`/`part-time`/`internship`/`working-student`/`thesis`) |
| Anzeige URL | `posting.url` |
| posting file, if copied | `posting.archive` - relative to the application: `posting/<file>`. `posting.fetched` = today |
| Bewerbungsfrist / deadline | `posting.deadline` (`"YYYY-MM-DD"`) |
| Stelle section (requirements) | `posting.notes` - a short paraphrase of what they ask for, not the posting text |
| Basis / "Aufbau wie <company>" | `approach.based_on` - the slug of that earlier application |
| the letter's hook and lead | `approach.angle` - one or two sentences in your words: what the letter opens with, which experience it puts first |
| CV-Änderungen (confirmed) | `approach.cv` - one short item per applied change ("flagship project first in projects", "skill group Robotics added"). Not the text itself; that is in cv.yaml. |
| Lücken | `approach.gaps` - one item each, with how the letter handles it if it does |
| Bewerbung | `submission.method` (`portal`/`email`/`post`), `submission.url` if it differs from `posting.url` |
| Portalfragen | `submission.questions: [{question, answer}]` - verbatim, `answer: null` where the user fills it in |
| Ansprechpartner with contact details | `contacts: [{name, role, email, phone, notes}]`. None → `contacts: []`. |
| - | `status: draft`, `applied: null` - the user sets both when it goes out |
| - | `timeline`: keep the "Created" entry `new` wrote, add `{date: "<today>", event: "Built with cvforge from brief.md"}` |
| Hinweise, anything else | `notes` - a `>` block |
| a looked-up address | `notes` - one line: "Address looked up <date>: <address> - source <URL> (<how current>)". |

## cv.yaml (tailored copy)

Only for changes the brief marks as confirmed ("bestätigt", "confirmed"). Map
by meaning onto the existing structure (`schema/cv.schema.json`):

| Change | Where |
|---|---|
| Profile text | `profile:` - replace the whole `>` block with the given text. |
| Title / tagline | `meta.tagline` - only if the brief says to change it ("Titel unverändert" → leave it). |
| A line under a degree ("Relevant coursework: …") | that `education[]` entry's `highlights:` list, one item. |
| A bullet for a job or project | that entry's `highlights:` list, in the position the brief implies (default: last). |
| Reordering projects / experience | Reorder the list - file order is display order. |
| Add / remove a skill | the matching `skills[].items` group. A new item that fits no group → report, do not create a group unasked. |
| Anything with no field in the schema | Not applied; report it with the reason. |

Entries are identified by `id` (`msc-kit`, `fraunhofer-iosb`, …) - grep the copy
for the organisation or degree to find the right one.
