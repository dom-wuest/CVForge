# Brief format

The contract between the letter-writing chat (claude.ai Project) and
`/new-application` in Claude Code. Paste the block below into the Project's
instructions so every brief comes out in this shape. The skill also reads
free-form briefs, but every field missing here is one it has to ask about or
leave out.

The field names are German because the letter chat already writes them that
way; the skill maps by meaning, so English names work too.

---

## Paste into the claude.ai Project instructions

> When a letter is final, produce an **application brief** as one markdown file
> named `<company>-<role>.md`, with exactly these sections. Write `–` for
> anything unknown; never guess an address or a reference number.
>
> ```markdown
> # <Company> – <Job title>
>
> | Feld | Wert |
> |---|---|
> | Firma | Company name as it should appear in the address (legal form if known) |
> | Adresse | Street, postcode city[, country] as given in the posting – or – if the posting has none |
> | Ansprechpartner | Full name with Frau/Herr, or – |
> | Anrede | The exact first line of the letter, e.g. "Dear Hiring Team," |
> | Stelle | Job title exactly as posted |
> | Kennziffer | Reference number, or – |
> | Kennziffer-Bezeichnung | The posting's own word for it (Job-ID, Referenznummer, …), or – |
> | Quelle | Where the posting was found, as a phrase for the letter ("Ihre Anzeige auf StepStone vom 04.09.2026"), or – |
> | Anzeige-URL | URL, or – |
> | Bewerbungsfrist | YYYY-MM-DD, or – |
> | Sprache | Deutsch / Englisch |
> | Unterlagen | Cover letter + CV, plus each further document by its name (Masterzeugnis, Bachelorzeugnis, Arbeitszeugnis Fraunhofer IOSB, …), or "keine Zeugnisse" |
> | Bewerbung | How to apply: portal / email / post, plus every question the portal asks |
> | Anzeige-Datei | File name of the archived posting PDF, if any |
>
> ## Unternehmen
> Two or three sentences on the company.
>
> ## Stelle
> Two or three sentences on what the role involves.
>
> ## Cover Letter
> **<Subject line exactly as it should print>**
>
> <Salutation>
>
> <Paragraphs, separated by blank lines.>
>
> <Closing>
> <Name>
>
> ## CV-Änderungen (<lang>)
>
> **Bestätigt:**
> - <Section / entry>: <the change, with the exact new text in a quote block>
>
> **Optional (nicht bestätigt):**
> - <suggestion>
> ```

---

## Rules the skill relies on

- **Only the "Bestätigt" list is applied** to the tailored CV. Everything else
  is reported back as not applied. A change confirmed in conversation but left
  under "Optional" will not be made.
- **New text is quoted exactly** (a `>` quote block). Paraphrased instructions
  ("make FluidSim2D more concrete") cannot be applied literally and come back
  as not applied.
- **Name the entry** a change belongs to: "Education, M.Sc. Computer Science",
  "Experience, Fraunhofer IOSB", "Profile".
- **The letter text is final.** The skill copies it verbatim and only ever
  changes layout to fit one page. Edit wording in the chat, not after the build.
- **Document names should match the labels** in `private.yaml` `documents:`
  (e.g. "Masterzeugnis"). An unknown name stops the build with a question.
- **No address → looked up.** If the brief has none, the skill finds the
  company's office in the job's city (else the headquarters) from the imprint
  or an official register, and reports it as looked up for you to confirm.
  Give the address in the brief whenever the posting has one.
- **Hand over the brief together with the posting PDF.** Attach both to the
  `/new-application` message, or pass their paths. The skill asks for
  whichever is missing and never searches for it.
- **Say how the application is submitted** (Bewerbung: portal / email /
  post). Only an electronic application may fall back to the compact layout
  when the letter is too long.
