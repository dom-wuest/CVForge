// ─── components/header.typ ──────────────────────────────────────────────────
// Name, tagline and contact row on the left; circular photo top-right.
//
// The photo lives here rather than in the sidebar so its size is independent
// of the column width below. When meta.photo is null the `auto` column
// collapses to zero and the text takes the full width - no conditional.

#import "../theme.typ": theme
#import "contact.typ": contacts-from

#let header(name: "", tagline: "", photo: none, contacts: ()) = {
  grid(
    columns: (1fr, auto),
    column-gutter: theme.header.gutter,
    // right + top so the photo hangs from the top edge and lines up with the
    // name, instead of centring against the whole text block.
    align: (left + horizon, right + top),
    {
      text(
        size: theme.header.name-size,
        weight: "bold",
        tracking: theme.header.name-tracking,
        name,
      )
      v(theme.header.gap-name)
      text(size: theme.header.tagline-size, fill: theme.accent, tagline)
      v(theme.header.gap-tagline)
      contacts-from(contacts)
    },
    // clip + radius turns any content into a circular avatar
    if photo != none {
      block(clip: true, radius: 50%, stroke: theme.header.photo-stroke + theme.rail, photo)
    },
  )
  v(theme.header.gap-below)
}

// Builds the header from the resolved `meta` and `contacts`. The photo path is
// repo-relative in the data, so it is read with a leading slash against
// `--root .`.
#let header-from(meta, contacts) = {
  let photo = meta.at("photo", default: none)
  header(
    name: meta.name,
    tagline: meta.tagline,
    photo: if photo != none { image("/" + photo, width: theme.header.photo-size) },
    contacts: contacts,
  )
}
