// ─── sections/profile.typ ───────────────────────────────────────────────────
// The intro paragraph.

#let profile-section(text-body, labels) = {
  heading(level: 1, labels.profile)
  text-body
}
