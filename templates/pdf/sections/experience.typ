// ─── sections/experience.typ ────────────────────────────────────────────────
// Employment history on a solid timeline rail.
//
// Field access is snake_case throughout the sections: these are keys from the
// YAML, not Typst identifiers, and they must match build/cv-<lang>.json
// literally. Typst treats `a-b` and `a_b` as two different names.

#import "../components/timeline.typ": timeline, tl-entry
#import "../components/chips.typ": chips-from

#let experience-entry(entry) = tl-entry(
  start: entry.start_display,
  end: entry.end_display,
  ongoing: entry.ongoing,
  title: entry.role,
  org: entry.org,
  meta: entry.meta_line,
  {
    let highlights = entry.at("highlights", default: ())
    if highlights.len() > 0 { list(..highlights) }
    chips-from(entry.at("tags", default: ()))
  },
)

#let experience-section(entries, labels) = {
  heading(level: 1, labels.experience)
  timeline(..entries.map(experience-entry))
}
