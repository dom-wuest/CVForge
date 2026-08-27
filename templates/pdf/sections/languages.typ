// ─── sections/languages.typ ─────────────────────────────────────────────────
// Spoken languages. `level` arrives already in the file's own language.

#let languages-section(entries, labels) = {
  heading(level: 1, labels.languages)
  list(..entries.map(l => [#l.name (#l.level)]))
}
