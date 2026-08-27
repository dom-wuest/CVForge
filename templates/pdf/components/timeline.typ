// ─── components/timeline.typ ────────────────────────────────────────────────
// The dated rail that carries Experience, Education and Projects.
//
// Structure: a three-column grid — dates | rail gutter | content — with ONE
// vertical line spanning the whole grid, and a circular node placed on that
// line per row.

#import "../theme.typ": theme

// Returns the three cells of one row. Splatted into the grid with `..`.
//
// `end` is always a finished display string — the resolve step localises it,
// including the "Present"/"heute" of an ongoing entry. `ongoing` only decides
// whether to italicise it, so no language ever reaches this file.
#let tl-entry(
  start: "",
  end: "",
  ongoing: false,
  title: "",
  org: "",
  meta: none,
  hollow: false,
  body,
) = {
  let node = place(
    left + top,
    // Half the circle hangs into each column, centring it on the rail.
    dx: -theme.timeline.node-r,
    // Drops the circle to the first text baseline of the title.
    dy: theme.timeline.node-dy,
    circle(
      radius: theme.timeline.node-r,
      fill: if hollow { white } else { theme.accent },
      stroke: if hollow {
        theme.timeline.node-hollow-stroke + theme.accent
      } else {
        // White ring, so the rail does not appear to run through the node.
        theme.timeline.node-solid-stroke + white
      },
    ),
  )
  (
    // Dates stacked, so a long range never wraps mid-month. The right pad is
    // what keeps the node circle off the date text.
    align(right + top, pad(
      right: theme.timeline.date-pad,
      text(size: theme.timeline.date-size, fill: theme.muted, {
        start
        linebreak()
        if ongoing { text(style: "italic", end) } else { end }
      }),
    )),
    { node; box() }, // gutter cell: the node sits on the rail
    {
      text(weight: "bold", size: theme.timeline.title-size, title)
      if org != "" [ #text(fill: theme.muted)[ | #org] ]
      if meta != none {
        linebreak()
        text(size: theme.timeline.meta-size, fill: theme.muted, meta)
      }
      if body != none { block(above: theme.timeline.body-gap, body) }
    },
  )
}

// One `grid.vline` spanning the whole grid, NOT a segment per row. This is what
// makes the rail survive a page break — per-entry strokes leave gaps at the
// boundary and restart at the wrong offset.
#let timeline(dashed: false, ..entries) = grid(
  columns: (theme.timeline.date-col, theme.timeline.gutter, 1fr),
  row-gutter: theme.timeline.row-gutter,
  grid.vline(
    x: 1,
    stroke: (
      paint: theme.rail,
      thickness: theme.timeline.rail,
      dash: if dashed { "dotted" } else { "solid" },
    ),
  ),
  ..entries.pos().flatten(),
)
