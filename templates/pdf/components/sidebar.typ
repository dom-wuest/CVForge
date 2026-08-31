// ─── components/sidebar.typ ─────────────────────────────────────────────────
// The two-column body: main content left, narrow aside right.
//
// The grid starts *after* the header, so the aside begins level with the first
// section heading whether or not there is a photo. That is the behaviour we
// want and it needs no special casing.

#import "../theme.typ": theme

// One `grid.vline` spanning the whole grid, not a segment per row - the same
// reason the timeline rail is one line: it survives a page break instead of
// restarting at the wrong offset.
#let two-column(main-body, aside-body) = grid(
  columns: (1fr, theme.sidebar.width),
  column-gutter: theme.sidebar.gutter,
  grid.vline(x: 1, stroke: theme.sidebar.rule + theme.rail),
  main-body,
  aside-body,
)
