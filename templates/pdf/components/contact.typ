// ─── components/contact.typ ─────────────────────────────────────────────────
// The contact line under the name: icon + text pairs separated by rules,
// wrapping automatically when they run out of width.

#import "../theme.typ": theme
#import "../icons.typ": icon-for

// The box() is load-bearing: without it the row can break between an icon and
// its own text, leaving a lone GitHub mark at the end of a line. Each item is
// short enough that forbidding an internal break costs nothing.
#let contact-item(name, body, url: none, brand: false) = {
  let inner = box[#icon-for(name, is-brand: brand, fill: theme.accent)#h(
      theme.contact.icon-gap,
    )#body]
  if url == none { inner } else { link(url, inner) }
}

#let contact-row(..items) = block(
  text(
    size: theme.contact.size,
    fill: theme.muted,
    items.pos().join([
      #h(theme.contact.sep-gap)#text(fill: theme.rail)[|]#h(theme.contact.sep-gap)
    ]),
  ),
)

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
