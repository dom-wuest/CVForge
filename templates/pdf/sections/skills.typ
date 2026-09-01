// ─── sections/skills.typ ────────────────────────────────────────────────────
// Two columns: right-aligned group label, then a row of chips.
//
// `skills` is a list of groups rather than a mapping precisely so this order is
// the order in the YAML file.

#import "../theme.typ": theme
#import "../components/bars.typ": rated-row
#import "../components/chips.typ": chip, chips-from

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
        chips-from(g.items.map(i => i.name)),
      ))
      .flatten()
  )
}

// Narrow form, for the sidebar: label on its own line with the items stacked
// beneath it. The wide `skills-section` above is kept for a future full-width
// or ATS-plain variant.
//
// An item with a `rating` drops the chip and becomes a label plus a bar - a
// chip with a bar next to it does not fit in 28mm, and the two treatments read
// as "this one is measurable, that one is a fact".
#let skill-items(items) = stack(
  dir: ttb,
  spacing: theme.sidebar.chip-gap,
  ..items.map(item => if item.rating == none {
    chip(item.name)
  } else {
    rated-row(
      text(size: theme.chip.size, weight: "semibold", fill: theme.ink, item.name),
      item.rating,
    )
  }),
)

#let skills-aside(groups, labels) = {
  heading(level: 1, labels.skills)
  for (i, g) in groups.enumerate() {
    block(
      above: if i == 0 { 0em } else { theme.sidebar.group-gap },
      below: 0em,
      // One stack, so the gap under the label is exactly `label-gap`. Emitting
      // the label as a paragraph and the items as a block let Typst's own
      // block spacing in underneath it *on top of* the explicit gap, which put
      // 3.2mm below the label against 2.1mm above - every group label sat
      // closer to the group above than to its own items.
      stack(
        dir: ttb,
        spacing: theme.sidebar.label-gap,
        text(size: theme.skills.label-size, weight: "semibold", fill: theme.muted, g.group),
        skill-items(g.items),
      ),
    )
  }
}
