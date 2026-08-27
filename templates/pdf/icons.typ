// ─── icons.typ ──────────────────────────────────────────────────────────────
// Wraps Font Awesome behind one function, so nothing else in the CV imports it
// directly. Swap the implementation here and the rest is untouched.
//
// REQUIREMENT: the fontawesome package maps names to code points but renders
// from the *desktop* OTF fonts — it does NOT bundle them. They are committed to
// assets/fonts/, and every compile must pass:
//     --font-path assets/fonts
// Without it you get "unknown font family: font awesome 7 free solid" and blank
// glyphs. The cvforge CLI passes it; see .vscode/settings.json for Tinymist.
//
// Flip FALLBACK to true to compile without the fonts (draws stub circles).

#import "theme.typ": theme

#let FALLBACK = false

#import "@preview/fontawesome:0.6.2": fa-icon

#let icon(name, solid: true, size: theme.contact.icon-size, fill: none) = {
  if FALLBACK {
    box(baseline: 0.15em, circle(radius: 0.32em, stroke: 0.6pt + fill))
  } else {
    // top-edge: "baseline" stops tall glyphs from inflating the line height
    box(fa-icon(name, solid: solid, size: size, fill: fill, top-edge: "baseline"))
  }
}

// Brand icons live in the Brands font, which has no solid variant.
#let brand(name, ..args) = icon(name, solid: false, ..args)

// Dispatches on the `brand` flag carried by each contact in the data, so the
// icon names in the YAML stay renderer-agnostic.
#let icon-for(name, is-brand: false, ..args) = {
  if is-brand { brand(name, ..args) } else { icon(name, ..args) }
}
