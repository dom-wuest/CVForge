// ─── sections/skills.typ ────────────────────────────────────────────────────
// Two columns: right-aligned group label, then a row of chips.
//
// `skills` is a list of groups rather than a mapping precisely so this order is
// the order in the YAML file.

#import "../theme.typ": theme
#import "../components/bars.typ": rated-entry
#import "../components/chips.typ": chip-run, chips-from

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
#let skill-items(items) = {
  // An item with a rating or a note gets a full-width row of its own; the rest
  // are chips. Consecutive chips are collected into one run so `chip-run` can
  // pack them onto shared rows when the layout asks for it - while keeping the
  // file's order, which is the display order everywhere else too.
  let blocks = ()
  let run = ()
  for item in items {
    if item.rating == none and item.note == none {
      run.push(item.name)
    } else {
      if run.len() > 0 {
        blocks.push(chip-run(run))
        run = ()
      }
      blocks.push(rated-entry(
        text(size: theme.chip.size, weight: "semibold", fill: theme.ink, item.name),
        rating: item.rating,
        note: item.note,
      ))
    }
  }
  if run.len() > 0 { blocks.push(chip-run(run)) }
  stack(dir: ttb, spacing: theme.sidebar.chip-gap, ..blocks)
}

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
