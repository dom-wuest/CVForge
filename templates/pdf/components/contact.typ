// ─── components/contact.typ ─────────────────────────────────────────────────
// The contact line under the name: icon + text pairs divided by thin rules.
//
// The row packs itself into lines rather than letting Typst's line breaker do
// it. To the breaker a separator is just more inline content, so a wrapped row
// keeps the "|" that happened to fall at the end of it — a divider dividing
// nothing. Measuring the items and deciding the line breaks here means a
// separator is only ever drawn between two items that really are side by side.

#import "../theme.typ": theme
#import "../icons.typ": icon-for

// The box() is load-bearing: without it the row can break between an icon and
// its own text, leaving a lone GitHub mark at the end of a line. Each item is
// short enough that forbidding an internal break costs nothing — and the
// packing below relies on each item having one definite width.
#let contact-item(name, body, url: none, brand: false) = {
  let inner = box[#icon-for(name, is-brand: brand, fill: theme.accent)#h(
      theme.contact.icon-gap,
    )#body]
  if url == none { inner } else { link(url, inner) }
}

#let contact-row(..items) = {
  let entries = items.pos()
  if entries.len() == 0 {
    return none
  }

  // `layout` hands us the width of the enclosing cell; the callback is a
  // context, so `measure` inside it sees the text style set just above.
  block(text(size: theme.contact.size, fill: theme.muted, layout(available => {
    let separator = [
      #h(theme.contact.sep-gap)#text(fill: theme.rail)[|]#h(theme.contact.sep-gap)
    ]
    let separator-width = measure(separator).width

    // Greedy packing: an item starts a new line when it plus the separator
    // that would precede it no longer fits.
    let lines = ()
    let line = ()
    let used = 0pt
    for entry in entries {
      let entry-width = measure(entry).width
      let needed = if line.len() == 0 { entry-width } else { separator-width + entry-width }
      if line.len() > 0 and used + needed > available.width {
        lines.push(line)
        line = (entry,)
        used = entry-width
      } else {
        line.push(entry)
        used += needed
      }
    }
    lines.push(line)

    stack(
      dir: ttb,
      spacing: theme.contact.row-gap,
      ..lines.map(l => l.join(separator)),
    )
  })))
}

// Builds the row straight from the resolved `contacts` array. Entries the
// resolve step marked private are already gone under profile=public, so there
// is nothing to filter here.
#let contacts-from(entries) = contact-row(
  ..entries.map(c => contact-item(
    c.icon,
    c.value,
    url: c.at("url", default: none),
    brand: c.at("brand", default: false),
  )),
)
