// ─── sections/skills.typ ────────────────────────────────────────────────────
// Two columns: right-aligned group label, then a row of chips.
//
// `skills` is a list of groups rather than a mapping precisely so this order is
// the order in the YAML file.

#import "../theme.typ": theme
#import "../components/chips.typ": chips-column, chips-from

#let skills-section(groups, labels) = {
  heading(level: 1, labels.skills)
  grid(
    columns: (auto, 1fr),
    column-gutter: theme.skills.column-gutter,
    row-gutter: theme.skills.row-gutter,
    ..groups
      .map(g => (
        align(right + horizon, text(
          size: theme.skills.label-size,
          weight: "semibold",
          fill: theme.muted,
          g.group,
        )),
        chips-from(g.items),
      ))
      .flatten()
  )
}

// Narrow form, for the sidebar: label on its own line with the chips stacked
// beneath it. The wide `skills-section` above is kept for a future full-width
// or ATS-plain variant.
#let skills-aside(groups, labels) = {
  heading(level: 1, labels.skills)
  for (i, g) in groups.enumerate() {
    block(above: if i == 0 { 0em } else { theme.sidebar.group-gap }, below: 0em, {
      text(size: theme.skills.label-size, weight: "semibold", fill: theme.muted, g.group)
      v(theme.sidebar.label-gap)
      chips-column(g.items)
    })
  }
}
