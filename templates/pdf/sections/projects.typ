// ─── sections/projects.typ ──────────────────────────────────────────────────
// Optional section. main.typ skips it when the data has no `projects` key.

#import "../theme.typ": theme
#import "../components/timeline.typ": timeline, tl-entry
#import "../components/chips.typ": chips-from

// For papers: the list in order, with the owner's own name in bold, which is
// how a publication list says "this one is me" without a footnote.
// `break_after` ends the line after that author's comma, so a hand-placed
// break never strands a comma at the start of the next line.
#let authors-line(authors) = text(size: theme.timeline.meta-size, fill: theme.muted, {
  for (i, author) in authors.enumerate() {
    if author.me { text(weight: "bold", fill: theme.ink, author.name) } else { author.name }
    if i < authors.len() - 1 {
      ","
      if author.break_after { linebreak() } else { " " }
    }
  }
})

#let projects-entry(entry) = tl-entry(
  start: entry.start_display,
  end: entry.end_display,
  ongoing: entry.ongoing,
  title: entry.name,
  org: "",
  meta: entry.meta_line,
  {
    if entry.authors.len() > 0 {
      authors-line(entry.authors)
      parbreak()
    }

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

    // A block, not bare inline chips: `summary` is a paragraph, so without this
    // the first chip is pulled up onto its last line whenever that line has
    // room for it.
    let tags = entry.at("tags", default: ())
    if tags.len() > 0 { block(above: theme.timeline.body-gap, chips-from(tags)) }
  },
)

#let projects-section(entries, labels) = {
  heading(level: 1, labels.projects)
  timeline(..entries.map(projects-entry))
}

// ─── Standalone projects page ───────────────────────────────────────────────
// Selected by `meta.projects_layout: page`. No sidebar here, so the full width
// is available and each entry gets a screenshot beside it. Same timeline rail
// as the CV page, so the two read as one document.

#let projects-page-entry(entry) = {
  let picture = entry.at("image", default: none)
  tl-entry(
    start: entry.start_display,
    end: entry.end_display,
    ongoing: entry.ongoing,
    title: entry.name,
    org: "",
    meta: entry.meta_line,
    aside: if picture != none {
      block(
        clip: true,
        radius: theme.projects.image-radius,
        stroke: theme.projects.image-stroke,
        image("/" + picture, width: theme.projects.image-width),
      )
    } else {
      // Reserve the column anyway, so an entry without a screenshot keeps the
      // same text width as the rest and the page reads as one list.
      box(width: theme.projects.image-width)
    },
    {
      if entry.authors.len() > 0 {
        authors-line(entry.authors)
        parbreak()
      }

      // Monospaced, because it is a repository path and reads as one. When
      // there is no repository yet, `url_note` says so in its place rather
      // than leaving the reader to wonder; beside a link it qualifies it
      // ("paper coming soon").
      let url = entry.at("url", default: none)
      let note = entry.at("url_note", default: none)
      if url != none {
        text(
          size: theme.projects.url-size,
          font: theme.mono-font,
          link(url, entry.at("url_label", default: url)),
        )
        if note != none {
          h(theme.projects.note-gap)
          text(size: theme.projects.url-size, style: "italic", fill: theme.muted, note)
        }
        parbreak()
      } else if note != none {
        text(size: theme.projects.url-size, style: "italic", fill: theme.muted, note)
        parbreak()
      }

      let summary = entry.at("summary", default: none)
      if summary != none { summary }

      let highlights = entry.at("highlights", default: ())
      if highlights.len() > 0 { list(..highlights) }

      let tags = entry.at("tags", default: ())
      if tags.len() > 0 { block(above: theme.timeline.body-gap, chips-from(tags)) }
    },
  )
}

#let projects-page(entries, labels) = {
  heading(level: 1, labels.projects)
  timeline(row-gutter: theme.projects.row-gutter, ..entries.map(projects-page-entry))
}
