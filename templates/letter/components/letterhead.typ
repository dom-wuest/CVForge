// ─── letter/components/letterhead.typ ───────────────────────────────────────
// Name, tagline and contact row, with a hairline under them.
//
// Deliberately not the CV's header-from(): no photo. The reader already has
// your photograph on the CV in the same envelope, and the 28mm it costs is
// 28mm this page does not have - everything here must fit above the address
// field at 45mm. What it does share is contacts-from(), so the contact row is
// the same component, from the same data, rendering the same way.

#import "../theme.typ": letter, theme
#import "../../pdf/components/contact.typ": contacts-from

#let letterhead(meta, contacts) = {
  text(
    size: letter.head.name-size,
    weight: "bold",
    tracking: letter.head.name-tracking,
    meta.name,
  )
  v(letter.head.gap-name)
  text(size: letter.head.tagline-size, fill: theme.accent, meta.tagline)
  v(letter.head.gap-tagline)
  contacts-from(contacts)
  v(letter.head.rule-gap)
  line(length: 100%, stroke: letter.head.rule + theme.rail)
}
