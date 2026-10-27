# Report template

Fill in every line; write "–" where something does not apply. Use ✅ / ⚠️ / ❌.
Overall status: ❌ if any step failed or a safety check failed, ⚠️ if the PDFs
were built but something needs the user (overflow, unapplied change, missing
posting, ambiguity, a looked-up address), ✅ otherwise. A looked-up address is
always ⚠️ and always listed under "Needs your input" - the user confirms it
before sending.

```markdown
## <slug> – <Company>, <Job title>

**Status: ✅ ready to send** | ⚠️ needs attention | ❌ failed

| Step | Result |
|---|---|
| `cvforge new` | ✅ --lang en [--cv] |
| address | ✅ from the brief / ⚠️ looked up: <address> – [source](<url>), current as of <date> |
| letter.yaml | ✅ layout din/compact, justify no/yes, subject override yes/no, salutation default/custom |
| dossier.yaml + brief.md | ✅ / posting archived: yes/no |
| cv.yaml (tailored) | ✅ N changes applied / – not tailored |
| `cvforge check` | ✅ no warnings for this application / ⚠️ <warnings> |
| `cvforge apply` | ✅ / ❌ <error> |

**Letter:** N page(s) ✅ / ⚠️ over one page
**CV:** N page(s), expected M ✅ / ⚠️ overflowed · source `applications/<slug>/cv.yaml` | `data/cv-<lang>.yaml`
**Attachments:** <labels in order> / none
**Send folder:** `out/applications/<slug>/` (N files)

**CV changes applied:**
- <entry>: <change>

**Not applied:**
- <change> – unconfirmed in the brief / no schema field / …

**Layout changes made to fit:** – / justify: true / layout: compact

**Needs your input:**
- <missing posting archive, ambiguous field, typo noticed in the letter text, portal questions to answer at upload>

**cvforge notes / warnings:** <verbatim, this application only>

**Visual check:** <one line each for letter and CV - what was looked at, anything off>

**Safety:** data/ unchanged ✅ · application gitignored ✅ · nothing staged or committed ✅
```
