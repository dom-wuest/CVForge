// ─── components/chips.typ ───────────────────────────────────────────────────
// Small rounded pills for technologies and focus areas.

#import "../theme.typ": theme

#let chip(body, tone: theme.accent) = box(
  fill: tone.lighten(theme.chip.bg-lighten),
  stroke: theme.chip.border + tone.lighten(theme.chip.border-lighten),
  radius: theme.chip.radius,
  inset: theme.chip.inset,
  // Expands the background without affecting layout, so line height stays
  // stable when chips appear inline with text.
  outset: theme.chip.outset,
  text(size: theme.chip.size, fill: tone.darken(theme.chip.text-darken), body),
)

// The trailing [ ] is a real space, so a long row can break between chips.
#let chips(..names) = names.pos().map(chip).join(h(theme.chip.gap) + [ ])

// `none` for an empty list, so callers can drop the block entirely rather than
// emitting an empty paragraph.
#let chips-from(names) = if names.len() == 0 { none } else { chips(..names) }

// Stacked one-per-row, for the narrow sidebar. Wrapping chips inline needs a
// column roughly 45mm wide; stacking them lets it be 28mm, and the width saved
// goes back to the main column where the tall content lives.
#let chips-column(names) = stack(
  dir: ttb,
  spacing: theme.sidebar.chip-gap,
  ..names.map(chip),
)
