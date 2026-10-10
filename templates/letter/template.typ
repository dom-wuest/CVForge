// ─── letter/template.typ ────────────────────────────────────────────────────
// One function wrapping the letter: page geometry, text defaults, the show
// rules, and the fold marks in the left margin.
//
// The CV's template.typ is not reused. It is not that the rules differ much -
// it is that they differ for different reasons: the CV's exist to make a dense
// two-column timeline readable, a letter's to make one column of prose read
// like a letter. Sharing them would couple two things that should be free to
// move apart. The theme, where the actual design decisions live, IS shared.

#import "theme.typ": letter, theme

// Fold and punch marks, drawn in the left margin against the paper's edges.
// `place` inside page(background:) measures from the page corner, which is
// exactly the frame DIN 5008's numbers are quoted in.
#let fold-marks() = {
  if not letter.fold.enabled {
    return none
  }
  let mark(y, length) = place(
    top + left,
    dx: letter.fold.x,
    dy: y,
    line(length: length, stroke: letter.fold.stroke + theme.rail),
  )
  mark(letter.fold.first, letter.fold.length)
  mark(letter.fold.punch, letter.fold.punch-length)
  mark(letter.fold.second, letter.fold.length)
}

// `folds: false` for the compact layout: marks for an envelope the letter
// will never see are just stray lines in the margin.
#let letter-template(lang: "de", folds: true, doc) = {
  set page(
    paper: letter.page.paper,
    margin: letter.page.margin,
    background: if folds { fold-marks() },
    // A cover letter is one page; the footer exists only so a two-page one is
    // obviously wrong rather than quietly wrong.
    footer: context {
      if counter(page).final().first() > 1 {
        align(center, text(
          size: theme.page.footer-size,
          fill: theme.muted,
          counter(page).display("1 / 1", both: true),
        ))
      }
    },
  )

  set text(font: theme.body-font, size: theme.size, fill: theme.ink, lang: lang)
  set par(
    justify: false, // ragged right; justified prose in a letter reads as a form
    leading: letter.body.leading,
    spacing: letter.body.par-spacing,
  )

  show link: it => text(fill: theme.accent, it)
  show strong: it => text(weight: "semibold", fill: theme.accent.darken(15%), it)

  doc
}
