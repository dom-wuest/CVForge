// ─── sections/languages.typ ─────────────────────────────────────────────────
// Spoken languages. `level` arrives already in the file's own language.

#import "../theme.typ": theme

#let languages-section(entries, labels) = {
  heading(level: 1, labels.languages)
  list(..entries.map(l => [#l.name (#l.level)]))
}

// Narrow form, for the sidebar: name over level, since "verhandlungssicher"
// alongside "Englisch" does not fit in 28mm.
#let languages-aside(entries, labels) = {
  heading(level: 1, labels.languages)
  for l in entries {
    text(size: theme.h2.size * 0.9, weight: "semibold", l.name)
    linebreak()
    text(size: theme.timeline.meta-size, fill: theme.muted, l.level)
    linebreak()
    v(theme.sidebar.entry-gap)
  }
}
