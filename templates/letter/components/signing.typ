// ─── letter/components/signing.typ ──────────────────────────────────────────
// Closing formula, signature, typed name, enclosures.
//
// The signature image is optional and its absence is not an error: on a fresh
// clone, in CI, or before you have scanned one, the letter renders with the
// typed name and blank space above it, which is exactly what you want if you
// intend to print and sign it. That is the same promise data/private.yaml
// makes for the phone number - the build never depends on a private file
// existing.
//
// The image is loaded root-absolutely ("/" + path) against `--root .`, the
// same way the CV loads its avatar.

#import "../theme.typ": letter, theme

#let signing(closing, name, signature: none, enclosures: (), enclosures-label: none) = {
  // `block(breakable: false)` keeps the closing, the signature and the name
  // together. Splitting a signature across a page break is the one layout
  // failure a reader would actually notice.
  block(breakable: false, {
    v(letter.sign.above)
    closing
    v(letter.sign.image-gap)
    if signature == none {
      v(letter.sign.blank-height)
    } else {
      // Left-aligned in a fixed box, so the typed name below it does not shift
      // sideways when you rescan the signature at a different size.
      box(
        width: letter.sign.image-width,
        height: letter.sign.image-height,
        align(left + horizon, image(
          "/" + signature,
          width: 100%,
          height: 100%,
          fit: "contain",
        )),
      )
      v(letter.sign.name-gap)
    }
    name
  })

  if enclosures.len() > 0 {
    v(letter.sign.enclosures-above)
    text(size: letter.sign.enclosures-size, fill: theme.muted, {
      if enclosures-label != none [#enclosures-label: ]
      enclosures.join(", ")
    })
  }
}
