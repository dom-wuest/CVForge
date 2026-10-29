// ─── letter/main.typ ────────────────────────────────────────────────────────
// Document assembly only: read the resolved JSON, apply the template, place
// the blocks in order. No content and no styling live here.
//
// Compile through the CLI, which passes the flags this always needs:
//     uv run cvforge letter <slug>
// or directly:
//     typst compile templates/letter/main.typ out/letter.pdf \
//         --root . --font-path assets/fonts --input slug=<slug>
//
// --root .  is what makes the absolute /build/... path below resolve to the
// repo root; --font-path is what makes Font Awesome render at all.
//
// LIVE PREVIEW: Tinymist's --input flags are set once for the whole workspace
// (.vscode/settings.json), so they cannot name the slug you happen to be
// editing. `cvforge dev --letter <slug>` mirrors the resolved artifact to
// build/letter-preview.json, which is the default below - so the preview
// always shows whatever the watcher is currently on.

#import "template.typ": letter-template
#import "theme.typ": letter as letter-theme
#import "components/letterhead.typ": letterhead
#import "components/address.typ": address-band
#import "components/signing.typ": signing
#import "../pdf/components/marker.typ": flow-marker, height-marker

#let slug = sys.inputs.at("slug", default: "preview")
#let doc = json("/build/letter-" + slug + ".json")

// `din` places the blocks against the paper for a window envelope; `compact`
// flows them for a letter that only ever travels as a PDF. Artifacts built
// before the key existed have no `layout`, hence the default.
#let compact = doc.meta.at("layout", default: "din") == "compact"

// The letter's own language wins over the workspace-wide --input lang, which
// says "en" no matter which letter is open in the editor.
#show: letter-template.with(
  lang: doc.meta.lang,
  folds: not compact,
  justify: doc.meta.at("justify", default: false),
)

// Both blocks above the body are PLACED, not flowed, so neither can push the
// other down: the letterhead hangs from the top of the text area, the address
// field from 45mm on the paper, and the body starts at 98.46mm on the paper -
// three fixed positions rather than a stack of accumulated heights. Placed
// content advances no cursor, which is what lets the `v()` below measure from
// the top of the text area rather than from wherever the letterhead ended.
//
// The letterhead must therefore FIT in what is left above the address field;
// it will not make room for itself. See components/address.typ.
//
// The compact layout drops all of that: the three blocks flow, so each starts
// where the previous one ended, plus a fixed gap.
//
// For `cvforge`'s layout report: how much of its budget the letterhead uses.
// Measured, not placed in the flow - it prints nothing either way.
#height-marker(
  "cvforge-letterhead",
  letterhead(doc.meta, doc.sender.contacts),
  letter-theme.address.top - letter-theme.page.margin.top,
)
#if compact {
  block(width: 100%, letterhead(doc.meta, doc.sender.contacts))
  v(letter-theme.compact.address-gap)
  address-band(doc.sender, doc.recipient, doc.info, none)
  v(letter-theme.compact.body-gap)
} else {
  place(top + left, dy: 0pt, block(width: 100%, letterhead(doc.meta, doc.sender.contacts)))
  address-band(
    doc.sender,
    doc.recipient,
    doc.info,
    letter-theme.address.top - letter-theme.page.margin.top,
  )
  // The flow starts here, at a fixed height, so the subject line sits on the
  // same baseline in every letter you ever send.
  v(letter-theme.body.top - letter-theme.page.margin.top)
}

#align(right, text(size: letter-theme.date.size, {
  if doc.sender.address.city != none [#doc.sender.address.city, ]
  doc.meta.date_display
}))
#v(letter-theme.date.below)

// No "Betreff:" label - DIN 5008 dropped it, and bold already says what it is.
#text(size: letter-theme.subject.size, weight: "bold", doc.subject)
#v(letter-theme.subject.below)

#doc.salutation
#v(letter-theme.salutation.below)

#for paragraph in doc.body {
  paragraph
  parbreak()
}

#signing(
  doc.closing,
  doc.meta.name,
  signature: doc.sender.at("signature", default: none),
  enclosures: doc.enclosures,
  enclosures-label: doc.labels.enclosures,
)

// For `cvforge`'s layout report: where the letter ended. Prints nothing.
#flow-marker("cvforge-letter-end", letter-theme.page.margin)
