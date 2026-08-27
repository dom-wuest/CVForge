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
#import "sections/profile.typ": profile-section
#import "sections/experience.typ": experience-section
#import "sections/education.typ": education-section
#import "sections/projects.typ": projects-section
#import "sections/skills.typ": skills-section
#import "sections/languages.typ": languages-section

#let lang = sys.inputs.at("lang", default: "en")
#let cv = json("/build/cv-" + lang + ".json")
#let labels = cv.labels

#show: cv-template.with(lang: lang)

#header-from(cv.meta, cv.contacts)

// `cv.sections` is the list of sections that actually have content, in display
// order, computed during resolve. Dispatching off it means an empty or absent
// section disappears from the PDF with no `if` per section here.
#let renderers = (
  profile: () => profile-section(cv.profile, labels),
  experience: () => experience-section(cv.experience, labels),
  education: () => education-section(cv.education, labels),
  projects: () => projects-section(cv.projects, labels),
  skills: () => skills-section(cv.skills, labels),
  languages: () => languages-section(cv.languages, labels),
)

#for name in cv.sections {
  (renderers.at(name))()
}
