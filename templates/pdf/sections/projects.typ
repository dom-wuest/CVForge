// ─── sections/projects.typ ──────────────────────────────────────────────────
// Optional section. main.typ skips it when the data has no `projects` key.

#import "../theme.typ": theme
#import "../components/timeline.typ": timeline, tl-entry
#import "../components/chips.typ": chips-from

#let projects-entry(entry) = tl-entry(
  start: entry.start_display,
  end: entry.end_display,
  ongoing: entry.ongoing,
  title: entry.name,
  org: "",
  meta: entry.meta_line,
  {
    let summary = entry.at("summary", default: none)
    if summary != none { summary }

    let highlights = entry.at("highlights", default: ())
    if highlights.len() > 0 { list(..highlights) }

    let url = entry.at("url", default: none)
    if url != none {
      block(above: theme.timeline.body-gap, text(
        size: theme.timeline.meta-size,
        link(url, entry.at("url_label", default: url)),
      ))
    }

    chips-from(entry.at("tags", default: ()))
  },
)

#let projects-section(entries, labels) = {
  heading(level: 1, labels.projects)
  timeline(..entries.map(projects-entry))
}
