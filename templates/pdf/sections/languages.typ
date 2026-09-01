// ─── sections/languages.typ ─────────────────────────────────────────────────
// Spoken languages. `level` arrives already in the file's own language.

#import "../theme.typ": theme
#import "../components/bars.typ": rated-row

#let languages-section(entries, labels) = {
  heading(level: 1, labels.languages)
  list(..entries.map(l => [#l.name (#l.level)]))
}

// Narrow form, for the sidebar: name over level, since "verhandlungssicher"
// alongside "Englisch" does not fit in 28mm. An optional `rating` puts a bar
// on the name row - this is where a bar earns its place, because CEFR-ish
// words like "fluent" are vague in a way a scale is not.
#let languages-aside(entries, labels) = {
  heading(level: 1, labels.languages)
  for (i, l) in entries.enumerate() {
    let name = text(size: theme.h2.size * 0.9, weight: "semibold", l.name)
    block(
      above: if i == 0 { 0em } else { theme.sidebar.group-gap },
      below: 0em,
      stack(
        dir: ttb,
        spacing: theme.sidebar.entry-gap,
        if l.rating == none { name } else { rated-row(name, l.rating) },
        text(size: theme.timeline.meta-size, fill: theme.muted, l.level),
      ),
    )
  }
}
