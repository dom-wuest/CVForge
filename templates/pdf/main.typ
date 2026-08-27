// ─── main.typ ───────────────────────────────────────────────────────────────
// STEP 3 of the build order: the demo split into modules, content still
// hardcoded. Step 4 replaces this body with calls into sections/*.typ driven by
// build/cv-<lang>.json.

#import "theme.typ": theme
#import "template.typ": cv-template
#import "components/header.typ": header
#import "components/contact.typ": contact-item
#import "components/chips.typ": chips
#import "components/timeline.typ": timeline, tl-entry

#show: cv-template.with(lang: "en")

#header(
  name: "Dominik Wüst",
  tagline: "M.Sc. Computer Science – Machine Learning & Rendering Engineer",
  photo: image("/assets/avatar.jpg", width: theme.header.photo-size),
  contacts: (
    (icon: "envelope", value: [kontakt\@dom-wuest.de], url: "mailto:kontakt@dom-wuest.de"),
    (icon: "phone", value: [+49 000 0000000]),
    (icon: "location-dot", value: [Karlsruhe, DE]),
    (icon: "linkedin", brand: true, value: [dom-wuest], url: "https://linkedin.com/in/dom-wuest"),
    (icon: "github", brand: true, value: [dom-wuest], url: "https://github.com/dom-wuest"),
    (icon: "globe", value: [dom-wuest.de], url: "https://dom-wuest.de"),
  ),
)

= Profile

Computer Science graduate specializing in real-time computer graphics, GPU
programming and machine learning. Experienced in C++, Vulkan and Python through
research at KIT and Fraunhofer IOSB. Interested in neural rendering,
differentiable graphics and computer vision.

= Experience

#timeline(
  tl-entry(
    start: "Oct 2021", end: "Mar 2026",
    title: "Research Assistant",
    org: "Fraunhofer IOSB",
    meta: "Karlsruhe, Germany",
  )[
    - Applied pretrained computer vision models for object detection, segmentation, image retrieval, and vision-language embeddings to accelerate Structure-from-Motion pipelines
    - Deployed deep learning models in C++ using ONNX Runtime and clip.cpp, converting models to ONNX and modifying computation graphs to support dynamic batch sizes and image resolutions
    - Developed and shipped cross-platform software and maintained CI/CD pipelines using GitLab and Docker
    #chips("C++", "Qt", "OpenCV", "ONNX Runtime")
  ],
  tl-entry(
    start: "May 2025", end: "Aug 2025",
    title: "Research Assistant",
    org: "Karlsruhe Institute of Technology (IVD)",
    meta: "Karlsruhe, Germany",
  )[
    - Contributed to a LLM-based shader optimization pipeline by integrating the Falcor renderer and adding support for cooperative vector acceleration
    - Designed related LLM prompts and analyzed proposed optimizations automatically
    - Co-author on related paper under submission
    #chips("Python", "C++", "Slang")
  ],
  tl-entry(
    start: "Nov 2020", end: "Jul 2021",
    title: "Student Assistant",
    org: "Karlsruhe Institute of Technology (CAPP)",
    meta: "Karlsruhe, Germany",
  )[
    - Tutored a group of students in computer engineering
    - Courses in fundamentals of microelectronics, design and construction of logic circuits
    #chips("LaTeX", "C", "Presentations")
  ],
)

= Education

#timeline(
  dashed: true,
  tl-entry(
    start: "2023", end: "Present", ongoing: true, hollow: true,
    title: "M.Sc. Computer Science",
    org: "Karlsruhe Institute of Technology (KIT)",
    meta: "Thesis: Automatic Shader Function Level of Detail using Neural Networks and Symbolic Regression – Current Grade 1.2",
  )[
    #chips("Computer Graphics", "Anthropomatics and Cognitive Systems")
  ],
  tl-entry(
    start: "2018", end: "2023", hollow: true,
    title: "B.Sc. Computer Science",
    org: "Karlsruhe Institute of Technology (KIT)",
    meta: "Thesis: Real-Time Neural Path-Guiding – Minor: Electrical Engineering – Grade 2.1",
  )[],
  tl-entry(
    start: "2015", end: "2018", hollow: true,
    title: "Allgemeine Hochschulreife",
    org: "Technisches Gymnasium Schwäbisch Hall",
    meta: "Specialization: Computer Science – Grade 1.2",
  )[],
)

= Skills

#grid(
  columns: (auto, 1fr),
  column-gutter: theme.skills.column-gutter,
  row-gutter: theme.skills.row-gutter,
  ..(
    ("Languages", ("C++", "Python")),
    ("Graphics", ("Vulkan", "Slang", "GLSL")),
    ("ML", ("PyTorch", "CUDA", "ONNX Runtime", "tiny-cuda-nn")),
    ("Computer Vision", ("OpenCV", "OpenMMLab", "clip.cpp")),
    ("Frameworks & UI", ("Qt", "ImGui", "React", "HTML/CSS")),
    ("Tooling", ("Docker", "CMake", "GitLab CI/CD")),
  )
    .map(((label, items)) => (
      align(right + horizon, text(
        size: theme.skills.label-size,
        weight: "semibold",
        fill: theme.muted,
        label,
      )),
      chips(..items),
    ))
    .flatten()
)

= Languages
- German (native)
- English (fluent)
