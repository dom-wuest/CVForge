// ─── sections/languages.typ ─────────────────────────────────────────────────
// Spoken languages. `level` arrives already in the file's own language.

#import "../theme.typ": theme
#import "../components/bars.typ": rated-entry

#let languages-section(entries, labels) = {
  heading(level: 1, labels.languages)
  list(..entries.map(l => [#l.name (#l.level)]))
}

// Narrow form, for the sidebar: name over level, since "verhandlungssicher"
// alongside "Englisch" does not fit in 28mm. An optional `rating` puts a bar on
// the name row - this is where a bar earns its place, because words like
// "fluent" are vague in a way a scale is not.
//
// Structurally identical to a rated skill, and shares `rated-entry` with it.
#let languages-aside(entries, labels) = {
  heading(level: 1, labels.languages)
  for (i, l) in entries.enumerate() {
    block(
      above: if i == 0 { 0em } else { theme.sidebar.group-gap },
      below: 0em,
      rated-entry(
        text(size: theme.h2.size * 0.9, weight: "semibold", l.name),
        rating: l.rating,
        note: l.level,
      ),
    )
  }
}
