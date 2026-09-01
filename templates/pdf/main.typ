// ─── main.typ ───────────────────────────────────────────────────────────────
// Document assembly only: read the resolved JSON, apply the template, call the
// sections in order. No content and no styling live here.
//
// Compile through the CLI, which passes the flags this always needs:
//     uv run cvforge pdf --lang en
// or directly:
//     typst compile templates/pdf/main.typ out/cv-en.pdf \
//         --root . --font-path assets/fonts --input lang=en
//
// --root .  is what makes the absolute /build/... path below resolve to the
// repo root; --font-path is what makes Font Awesome render at all.

#import "template.typ": cv-template
#import "components/header.typ": header-from
#import "components/sidebar.typ": two-column
#import "sections/profile.typ": profile-section
#import "sections/experience.typ": experience-section
#import "sections/education.typ": education-section
#import "sections/projects.typ": projects-page, projects-section
#import "sections/skills.typ": skills-aside
#import "sections/languages.typ": languages-aside

#let lang = sys.inputs.at("lang", default: "en")
#let cv = json("/build/cv-" + lang + ".json")
#let labels = cv.labels

#show: cv-template.with(lang: lang)

// Full width: name, tagline, contacts, and the photo top-right.
#header-from(cv.meta, cv.contacts)

// Which sections go where. Skills and Languages are short and narrow, so they
// pay for a sidebar; the timeline-shaped sections stay in the main column,
// where every millimetre of width saves height.
#let MAIN-SECTIONS = ("profile", "experience", "education", "projects")
#let ASIDE-SECTIONS = ("skills", "languages")

#let renderers = (
  profile: () => profile-section(cv.profile, labels),
  experience: () => experience-section(cv.experience, labels),
  education: () => education-section(cv.education, labels),
  projects: () => projects-section(cv.projects, labels),
  skills: () => skills-aside(cv.skills, labels),
  languages: () => languages-aside(cv.languages, labels),
)

// `cv.sections` is the list of sections that actually have content, in display
// order, computed during resolve. Filtering it into the two columns keeps the
// property that an empty or absent section disappears with no `if` here.
#let render(names) = {
  for name in cv.sections.filter(n => n in names) {
    (renderers.at(name))()
  }
}

#two-column(render(MAIN-SECTIONS), render(ASIDE-SECTIONS))

// Projects get a page of their own when the data asks for it: full width, no
// sidebar, and room for a screenshot beside each entry. It stays part of this
// document, so the running footer numbers it with the rest.
//
// `resolve` has already dropped `projects` from `cv.sections` for this layout,
// so nothing renders twice, and removed the key entirely for layout "off".
#if cv.meta.projects_layout == "page" and cv.at("projects", default: ()).len() > 0 {
  pagebreak()
  projects-page(cv.projects, labels)
}
