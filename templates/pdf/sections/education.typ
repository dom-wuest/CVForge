// ─── sections/education.typ ─────────────────────────────────────────────────
// Degrees on a dotted rail with hollow nodes, to read as a different track
// from the solid Experience one.
//
// The meta line ("Thesis: ... – Minor: ... – Current Grade 1.2") is composed in
// resolve.py, not here: it has to skip absent fields without leaving a dangling
// separator, and the HTML renderer needs the identical string.

#import "../components/timeline.typ": timeline, tl-entry
#import "../components/chips.typ": chips-from

#let education-entry(entry) = tl-entry(
  start: entry.start_display,
  end: entry.end_display,
  ongoing: entry.ongoing,
  hollow: true,
  title: entry.degree,
  org: entry.org,
  meta: entry.meta_line,
  {
    let highlights = entry.at("highlights", default: ())
    if highlights.len() > 0 { list(..highlights) }
    chips-from(entry.at("tags", default: ()))
  },
)

#let education-section(entries, labels) = {
  heading(level: 1, labels.education)
  timeline(dashed: true, ..entries.map(education-entry))
}
