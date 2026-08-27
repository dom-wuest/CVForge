// ─── template.typ ───────────────────────────────────────────────────────────
// One function wrapping the whole document: page geometry, text defaults and
// the show rules that give headings, links and chips their look.
//
//   `set`  changes a default.
//   `show` intercepts and transforms.

#import "theme.typ": theme

#let cv-template(lang: "en", doc) = {
  set page(
    paper: theme.page.paper,
    margin: theme.page.margin,
    // Running footer, numbered only from page 2 onward — a one-page CV should
    // not carry "1 / 1", and page 1 of a CV never needs the reminder.
    footer: context {
      if counter(page).get().first() > 1 {
        align(
          center,
          text(
            size: theme.page.footer-size,
            fill: theme.muted,
            counter(page).display("1 / 1", both: true),
          ),
        )
      }
    },
  )

  set text(font: theme.body-font, size: theme.size, fill: theme.ink, lang: lang)
  set par(justify: false, leading: theme.leading, spacing: theme.par-spacing)
  set list(
    marker: text(fill: theme.accent, sym.bullet),
    indent: theme.list.indent,
    spacing: theme.list.spacing,
  )

  // Section headings: small caps, accent colour, hairline rule underneath.
  show heading.where(level: 1): it => block(
    above: theme.h1.above,
    below: theme.h1.below,
    {
      text(
        size: theme.h1.size,
        weight: "bold",
        fill: theme.accent,
        tracking: theme.h1.tracking,
        upper(it.body),
      )
      v(theme.h1.rule-gap)
      line(length: 100%, stroke: theme.h1.rule + theme.rail)
    },
  )

  show heading.where(level: 2): it => text(size: theme.h2.size, weight: "bold", it.body)

  // Links take the accent colour but stay underline-free in print.
  show link: it => text(fill: theme.accent, it)

  // Inline code / tech terms.
  show raw.where(block: false): it => box(
    fill: theme.chip-bg,
    inset: theme.code.inset,
    outset: theme.code.outset,
    radius: theme.code.radius,
    text(font: theme.mono-font, size: theme.code.size, it),
  )

  // `strong` (**bold**) picks up the accent automatically.
  show strong: it => text(weight: "semibold", fill: theme.accent.darken(15%), it)

  doc
}
