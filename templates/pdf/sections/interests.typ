// ─── sections/interests.typ ─────────────────────────────────────────────────
// Sidebar only. Plain chips - there is nothing to rate here, and a bar against
// "Hiking" would be absurd.
//
// Deliberately non-technical in the data: rendering, graphics and AI are
// already the tagline, the profile, the skills and every project, so listing
// them again spends lines proving something the CV has proved four times.

#import "../components/chips.typ": chip-run

#let interests-aside(items, labels) = {
  heading(level: 1, labels.interests)
  chip-run(items)
}
