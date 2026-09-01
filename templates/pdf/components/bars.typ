// ─── components/bars.typ ────────────────────────────────────────────────────
// A small proficiency bar, for the few items where a rating says something a
// chip cannot — spoken languages, and the one or two languages you actually
// write every day.
//
// Opt-in per item via `rating` in the data. Everything else stays a chip: bars
// against every skill turn into wallpaper, and an unfilled bar invites the
// reader to wonder what the missing fifth is.

#import "../theme.typ": theme

// Fixed width regardless of rating, so the filled fraction is comparable
// between rows. A bar whose *total* length varied would be unreadable.
#let level-bar(rating) = {
  let filled = calc.clamp(rating / theme.bar.scale, 0.0, 1.0)
  box(width: theme.bar.width, height: theme.bar.height, {
    place(left + horizon, rect(
      width: 100%,
      height: 100%,
      radius: theme.bar.radius,
      stroke: none,
      fill: theme.accent.lighten(theme.bar.track-lighten),
    ))
    place(left + horizon, rect(
      width: filled * 100%,
      height: 100%,
      radius: theme.bar.radius,
      stroke: none,
      fill: theme.accent,
    ))
  })
}

// Label left, bar right-aligned at a fixed width. `horizon` on both so the bar
// centres against the label's x-height rather than sitting on the baseline.
//
// The vertical pad is the chip's own inset. A chip carries that padding inside
// its box; a bare label does not, so without this a rated row sits 6pt tighter
// than the chips above and below it and the group loses its rhythm.
#let rated-row(label, rating) = pad(y: theme.chip.inset.y, grid(
  columns: (1fr, auto),
  column-gutter: theme.bar.gap,
  align: (left + horizon, right + horizon),
  label,
  level-bar(rating),
))
