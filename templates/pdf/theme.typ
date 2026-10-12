// ─── theme.typ ──────────────────────────────────────────────────────────────
// Every tunable in one place — this file is the CV's "CSS variables".
//
// It imports nothing, so any module can depend on it without a cycle. The rule
// that keeps it useful: no magic numbers anywhere else. If a component needs a
// constant, it becomes a key here.
//
// This is NOT shared with templates/web/cv.css. Web is scroll, not A4, and the
// stylesheet there is tuned to the host site. The two only have to cover the
// same data.

#let accent = rgb("#2b6cb0")

#let theme = (
  // ── Colour ────────────────────────────────────────────────────────────────
  accent: accent,
  ink: rgb("#1a202c"),
  muted: rgb("#718096"),
  rail: accent.lighten(60%),
  chip-bg: accent.lighten(88%),

  // ── Typography ────────────────────────────────────────────────────────────
  // Both are committed to assets/fonts/, so no fallback list is needed — and
  // Typst warns once per unresolved name in a list, which would mean two
  // warnings on every keystroke in the Tinymist preview. A compile without
  // --font-path falls back to Typst's default and looks obviously wrong, which
  // is the behaviour we want anyway.
  body-font: "Inter",
  mono-font: "JetBrains Mono",
  size: 9.5pt,
  leading: 0.62em,
  par-spacing: 0.85em,

  // ── Page ──────────────────────────────────────────────────────────────────
  page: (
    paper: "a4",
    margin: (x: 17mm, top: 15mm, bottom: 16mm),
    footer-size: 7.5pt,
  ),

  // ── Headings ──────────────────────────────────────────────────────────────
  h1: (
    size: 10.5pt,
    tracking: 0.08em,
    above: 1.25em,
    below: 0.75em,
    rule: 0.7pt, // hairline under the heading
    rule-gap: -0.55em, // pulls the rule up against the text
  ),
  h2: (size: 10pt),

  // ── Bullet lists ──────────────────────────────────────────────────────────
  list: (indent: 0.4em, spacing: 0.55em),

  // ── Inline code / tech terms ──────────────────────────────────────────────
  code: (
    size: 0.9em,
    radius: 2pt,
    inset: (x: 3pt, y: 0pt),
    outset: (y: 3pt),
  ),

  // ── Header block ──────────────────────────────────────────────────────────
  header: (
    name-size: 22pt,
    name-tracking: -0.01em,
    tagline-size: 10.5pt,
    gutter: 1.2em, // between the text column and the photo
    // Equal to sidebar.width today, so the photo sits squarely above the
    // column - but kept a separate key so either can be retuned alone.
    photo-size: 28mm,
    photo-stroke: 2pt,
    gap-name: -0.5em, // tightens name -> tagline
    gap-tagline: 0.3em, // tagline -> contact row
    gap-below: 0.4em, // header -> first section
  ),

  // ── Contact row ───────────────────────────────────────────────────────────
  contact: (
    size: 8.5pt,
    icon-size: 0.95em,
    icon-gap: 0.4em, // icon -> its text
    sep-gap: 0.7em, // around the "|" separators
    row-gap: 0.45em, // between wrapped contact lines
  ),

  // ── Chips / skill pills ───────────────────────────────────────────────────
  chip: (
    size: 8pt,
    radius: 3pt,
    inset: (x: 5pt, y: 3pt),
    // Grows the background without affecting layout, so a line of chips keeps
    // the same height as a line of plain text.
    outset: (y: 1pt),
    gap: 3pt,
    bg-lighten: 88%,
    border-lighten: 55%,
    border: 0.5pt,
    text-darken: 20%,
  ),

  // ── Level bars ────────────────────────────────────────────────────────────
  // Optional per-item proficiency indicator, opt-in through a `rating` in the
  // data. Deliberately not automatic: a column of bars against every skill
  // says less than a few well-chosen ones, and invites the reader to wonder
  // what the missing two fifths are.
  bar: (
    scale: 5, // ratings are 1..5; the schema enforces it
    width: 11mm,
    height: 2.2pt,
    radius: 1.1pt,
    gap: 1.5mm, // label -> bar
    track-lighten: 80%, // the unfilled remainder
  ),

  // ── Timeline ──────────────────────────────────────────────────────────────
  timeline: (
    // Do not shrink this to buy width: at 4.5em "Mar 2026" and "May 2025"
    // wrap onto two lines. The sidebar is the place to reclaim width.
    date-col: 5.2em,
    gutter: 1.5em,
    row-gutter: 1.15em,
    node-r: 3.5pt,
    rail: 1.3pt,
    // Aligns the node circle to the first baseline of the title. Calibrated
    // against timeline.title-size — retune it if that changes.
    node-dy: 0.34em,
    node-hollow-stroke: 1.4pt,
    node-solid-stroke: 2pt, // white ring, so the rail does not show through
    // Keeps the node circle — which sits on the column boundary — from
    // colliding with the date text. Removing it reintroduces the overlap.
    date-pad: 0.7em,
    date-size: 8pt,
    // A single-date entry (start == end) prints one line. The date is 8pt
    // and the title 10pt, and both are top-aligned, so the smaller text
    // rides ~1.2mm above the node. This drops it back onto the node's
    // centre. Calibrated against date-size vs title-size; retune if either
    // changes. Two-line dates do not need it - the pair reads as centred.
    single-date-dy: 3.4pt,
    title-size: 10pt,
    meta-size: 8pt,
    body-gap: 0.5em, // title/meta -> body
    aside-gap: 6mm, // entry -> its right-hand aside (projects page)
  ),

  // ── Projects page ─────────────────────────────────────────────────────────
  // Only used by the standalone projects page, which has no sidebar and so has
  // room for a screenshot beside each entry.
  projects: (
    image-width: 50mm,
    image-radius: 2.5pt,
    // No frame: a border competes with the images' own edges, and a tinted
    // one fights any screenshot that is not white. Set e.g.
    // `0.5pt + rgb("#a8c6e4")` to bring it back.
    image-stroke: none,
    url-size: 8pt,
    note-gap: 0.8em, // link -> its `url_note`, when a project has both
    row-gutter: 1.9em, // looser than the CV timeline; these entries are taller
  ),

  // ── Skills grid ───────────────────────────────────────────────────────────
  skills: (
    label-size: 8.5pt,
    column-gutter: 1.2em,
    row-gutter: 0.7em,
  ),

  // ── Right sidebar (skills + languages) ────────────────────────────────────
  // Narrow on purpose. One chip per row is what lets it be this thin, and
  // every millimetre here is a millimetre the main column does not get: the
  // body text is the tall part of the page, so it pays for the width twice.
  sidebar: (
    // `width` is the whole column; `pad` is taken off the left for breathing
    // room, so the usable content width is width - pad = 28mm. Keep that 28mm
    // if you retune: it is what makes the widest chips ("ONNX Runtime",
    // "GitLab CI/CD") fit on one line.
    width: 33mm,
    pad: 4mm,
    // The rule is drawn at the start of the sidebar column, so `gutter` is the
    // air to its left and `pad` the air to its right. Keep them equal or the
    // rule looks stuck to one side - it sat 0.7mm off the sidebar text and
    // 6mm off the main column before these were split apart.
    gutter: 4mm,
    // Same 0.7pt + rail as the h1 underline, so the separator reads as part of
    // the existing system rather than as a new device.
    rule: 0.7pt,
    // "stacked" gives one chip per row - the layout the 28mm column was
    // sized for. "wrapped" packs as many per row as fit, which is denser
    // but leaves a ragged right edge on the longer names.
    chip-layout: "wrapped",
    group-gap: 1.0em, // between skill groups
    label-gap: 0.35em, // group label -> its chips
    chip-gap: 0.42em, // between stacked chips
    entry-gap: 0.35em, // between language entries
  ),
)
