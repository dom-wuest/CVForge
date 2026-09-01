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

// A run of chips laid out per theme.sidebar.chip-layout. The single place that
// reads the toggle, so skills and interests can never disagree about it.
#let chip-run(names) = {
  if names.len() == 0 {
    none
  } else if theme.sidebar.chip-layout == "wrapped" {
    // Wrapped chips break onto new lines on paragraph leading, which is looser
    // than the stacked gap. Matching them means "wrapped" is never taller than
    // "stacked" for the same content - it only ever saves rows, never costs
    // them, which is the whole point of the toggle.
    block({
      set par(leading: theme.sidebar.chip-gap)
      chips(..names)
    })
  } else {
    stack(dir: ttb, spacing: theme.sidebar.chip-gap, ..names.map(chip))
  }
}
