// ─── marker.typ ─────────────────────────────────────────────────────────────
// A point in the flow, recorded as metadata and never printed.
//
// `cvforge` reads these back with `typst eval 'query(...)'` to report how much
// room a build has left - "the letter ends 23 mm above the bottom margin",
// "the main column runs 4 mm into page 2" - as numbers, without rendering a
// page to an image. That is what lets an assistant fix an overflow from text
// alone.
//
// `place`d, so the marker takes no room in the flow: a marker that added
// paragraph spacing could itself push a page that fits exactly onto the next.
//
// `margin` is the caller's page margin from its own theme (it needs `top` and
// `bottom`), so this file holds no geometry of its own. `limit_mm` is where
// the flow may end on a page, `top_mm` where it resumes on the next. All
// positions are in mm from the top of the paper.

#let flow-marker(name, margin) = place(context {
  let here-pos = here().position()
  [#metadata((
      page: here-pos.page,
      y_mm: here-pos.y / 1mm,
      top_mm: margin.top / 1mm,
      limit_mm: (page.height - margin.bottom) / 1mm,
    ))#label(name)]
})

// How tall `body` comes out at the width it will actually get, against the
// height it is allowed. For a block that is placed and therefore cannot push
// anything aside when it grows - the letterhead above the address field.
#let height-marker(name, body, budget) = place(layout(size => {
  let height = measure(block(width: size.width, body)).height
  [#metadata((height_mm: height / 1mm, budget_mm: budget / 1mm))#label(name)]
}))

// How many lines `body` wraps into at the width it will actually get - for a
// block whose extra lines cost the flow below it, like a subject that wraps.
// A line count reads more directly than a height: "the subject takes two
// lines" says what to fix. Counted against one line of `probe`, which the
// caller sets in the same style as `body`, since only it knows that style -
// and with the gap between lines, `leading`, which defaults to the paragraph's.
#let lines-marker(name, body, probe, leading: auto) = place(layout(size => context {
  let height = measure(block(width: size.width, body)).height
  let line = measure(probe).height
  let leading = if leading == auto { par.leading.to-absolute() } else { leading.to-absolute() }
  let lines = calc.max(1, calc.round((height + leading) / (line + leading)))
  [#metadata((lines: lines, height_mm: height / 1mm))#label(name)]
}))
