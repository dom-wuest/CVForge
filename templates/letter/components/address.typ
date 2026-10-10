// ─── letter/components/address.typ ──────────────────────────────────────────
// The address field, the return line above it, and the info block beside it.
//
// ── The one thing to understand here ────────────────────────────────────────
// This block is positioned against the PAPER, not against the flow. DIN 5008
// puts the top of the address field 45mm from the top edge of the sheet, and
// that number is what makes the address appear in an envelope window after two
// folds. If the letterhead above it grows by a line, the address field must
// NOT move - the letterhead has to give way instead.
//
// So `address-field` is a fixed-height block placed at an absolute offset, and
// the flow resumes below it at `letter.body.top` regardless of what happened
// above. Nothing here reacts to content height, which is the point.
//
// The letterhead colliding with the address field is therefore a real
// possibility, and a silent one. `cvforge letter` catches the consequence
// (a two-page letter); trimming `sender_contacts` is the fix.

#import "../theme.typ": letter, theme

// The small line above the recipient, e.g.
//   Dominik Wüst · Musterstraße 1 · 76131 Karlsruhe
// Its job is to let an undeliverable letter be returned without being opened,
// which is why it is set small and muted rather than as part of the address.
#let return-line(body) = text(
  size: letter.address.return-size,
  fill: theme.muted,
  body,
)

// The recipient's own lines. Absent parts collapse; no entry renders as a
// blank line, so a company with no named person does not leave a gap.
#let recipient-lines(recipient) = {
  let city = (recipient.postal_code, recipient.city).filter(p => p != none).join(" ")
  let lines = (
    recipient.company,
    recipient.at("department", default: none),
    recipient.at("person", default: none),
    recipient.at("street", default: none),
    if city != none and city != "" { city },
    // Uppercase by postal convention: it is what sorting machines read when a
    // letter crosses a border.
    if recipient.at("country", default: none) != none { upper(recipient.country) },
  ).filter(l => l != none and l != "")

  set par(leading: letter.address.leading, spacing: letter.address.leading)
  stack(dir: ttb, spacing: letter.address.leading, ..lines)
}

// Kennziffer and where the posting was found. Two shapes, because a reference
// is a labelled value and a source is a whole phrase.
//
// The block is a fixed width so its rows align with each other on the left,
// and the caller hangs that block from the right - a ragged column of
// right-aligned rows would read as three unrelated fragments.
#let info-block(entries) = {
  if entries.len() == 0 {
    return none
  }
  block(width: letter.info.width, {
    // The caller hangs this block from the right; its rows are left-aligned
    // inside it. Without resetting align here they inherit the cell's `right`,
    // which pushes each label flush against its own value.
    set align(left)
    set text(size: letter.info.size)
    stack(
      dir: ttb,
      spacing: letter.info.row-gap,
      ..entries.map(e => if e.label == none {
        e.value
      } else {
        // `auto` on the label so it is exactly as wide as whatever the posting
        // calls its reference number, and `1fr` on the value so a long one
        // wraps inside the block instead of running off the page.
        grid(
          columns: (auto, 1fr),
          column-gutter: letter.info.label-gap,
          text(fill: theme.muted, e.label), e.value,
        )
      }),
    )
  })
}

// The whole band: address field left, info block right, both from the same
// top edge.
//
// `top-offset` is how far below the text area's top edge the field starts -
// the caller works it out from the page margin, because only it knows that.
// `none` flows the band instead of placing it: the compact layout, where
// there is no envelope window to hit and the band simply follows the
// letterhead.
#let address-band(sender, recipient, info, top-offset) = {
  let band = block(width: 100%, grid(
    columns: (letter.address.width, 1fr),
    align: (left + top, right + top),
    {
      return-line(sender.return_line)
      v(letter.address.return-gap)
      recipient-lines(recipient)
    },
    info-block(info),
  ))
  if top-offset == none { band } else { place(top + left, dy: top-offset, band) }
}
