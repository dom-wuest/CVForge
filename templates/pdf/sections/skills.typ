// ─── sections/skills.typ ────────────────────────────────────────────────────
// Two columns: right-aligned group label, then a row of chips.
//
// `skills` is a list of groups rather than a mapping precisely so this order is
// the order in the YAML file.

#import "../theme.typ": theme
#import "../components/chips.typ": chips-from

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
