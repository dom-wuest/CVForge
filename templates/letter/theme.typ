// ─── letter/theme.typ ───────────────────────────────────────────────────────
// The letter's tunables, on top of the CV's.
//
// It re-exports the CV theme unchanged and adds one `letter` dictionary, so a
// letter module imports exactly one theme and the two documents cannot drift
// apart on colour or typeface. The same rule applies here as there: no magic
// numbers anywhere else.
//
// ── Why these numbers ───────────────────────────────────────────────────────
// The geometry is DIN 5008 Form B, which is what a German window envelope and
// a document scanner both assume. The load-bearing part is that the address
// field's top edge sits 45mm from the top edge of the PAPER, not from the text
// area — fold the page in thirds and that block lands in the window. So those
// positions are placed absolutely, and only the flow below the subject line is
// ordinary layout. See address.typ.
//
// The three numbers you cannot move without breaking the envelope:
//   address.top   45mm    top of the address field
//   fold.first    87mm    first fold, at one third
//   fold.second  192mm    second fold
// Everything else is taste.

#import "../pdf/theme.typ": accent, theme as cv-theme

#let theme = cv-theme

#let letter = (
  // ── Page ──────────────────────────────────────────────────────────────────
  // Wider left margin than the CV: DIN 5008 wants 25mm, and it is also where
  // the fold and punch marks live.
  page: (
    paper: "a4",
    margin: (left: 25mm, right: 20mm, top: 12mm, bottom: 20mm),
  ),

  // ── Letterhead ────────────────────────────────────────────────────────────
  // Everything above the address field has to fit in 45mm - 12mm = 33mm. The
  // name at 18pt plus a tagline plus ONE contact row fits with room to spare;
  // a contact row that wraps to two lines does not. That is what
  // `sender_contacts` in the letter YAML is for.
  head: (
    name-size: 18pt,
    name-tracking: -0.01em,
    tagline-size: 10pt,
    gap-name: -0.35em, // name -> tagline
    gap-tagline: 0.35em, // tagline -> contact row
    rule: 0.7pt, // hairline under the whole block
    rule-gap: 0.7em,
  ),

  // ── Address field (Anschriftenfeld) ───────────────────────────────────────
  address: (
    top: 45mm, // from the PAPER's top edge - the envelope window
    width: 85mm,
    return-size: 6.5pt, // the small Rücksendeangabe line
    return-gap: 0.9em, // return line -> recipient block
    leading: 0.65em, // between the recipient's own lines
  ),

  // ── Info block, beside the address field ──────────────────────────────────
  // Sized so `address.width` + this + a gutter fits the 165mm content width,
  // and so a source phrase like "Ihre Anzeige auf StepStone vom 04.09.2026"
  // stays on one line.
  info: (
    width: 65mm,
    size: 8pt,
    // Gap between a label and its value, NOT a fixed tab stop. `reference_label`
    // is the posting's own wording - "Kennziffer", "Referenznummer", "Role ID" -
    // so its width is not knowable here, and a fixed column silently drew the
    // value on top of a label that outgrew it.
    label-gap: 1.2em,
    row-gap: 0.45em,
  ),

  // ── Body ──────────────────────────────────────────────────────────────────
  // 98.46mm is where DIN 5008 Form B starts the subject line. It is an odd
  // number because it is nine lines of 4.23mm below the address field.
  body: (
    top: 98.46mm, // from the PAPER's top edge
    leading: 0.65em,
    par-spacing: 1.0em,
  ),

  date: (size: 9.5pt, below: 1.4em),

  subject: (size: 10.5pt, below: 1.5em),

  salutation: (below: 1.1em),

  // ── Signature ─────────────────────────────────────────────────────────────
  sign: (
    above: 1.6em, // last paragraph -> closing formula
    // Both bounds are set, and the image is fitted inside them: a signature
    // scan is whatever aspect ratio the scanner produced, and an unconstrained
    // height is how a tall crop silently pushes the letter onto a second page.
    image-width: 40mm,
    image-height: 14mm,
    image-gap: 0.5em, // closing formula -> the scan
    name-gap: 0.2em, // scan -> typed name
    // Reserved when there is no signature image, so a letter built without one
    // still leaves the space a handwritten signature would go in - you can
    // print it and sign by hand.
    blank-height: 12mm,
    enclosures-above: 1.8em,
    enclosures-size: 8.5pt,
  ),

  // ── Fold and punch marks ──────────────────────────────────────────────────
  // Thin rules in the left margin. They are what make folding by hand land the
  // address in the window on the first try.
  fold: (
    enabled: true, // not `show` - that is a keyword, and a bare one here is a parse error
    x: 8mm, // from the paper's left edge
    length: 4mm,
    punch-length: 6mm, // the hole-punch mark is longer, by convention
    first: 87mm,
    second: 192mm,
    punch: 148.5mm,
    stroke: 0.4pt,
  ),
)
