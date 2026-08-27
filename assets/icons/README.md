# Icons (HTML renderer)

Empty on purpose — populated when the HTML renderer is implemented.

The PDF renderer draws icons from the Font Awesome *webfont* via
`templates/pdf/icons.typ`. The HTML renderer must not: a webfont is a bad fit
for a fragment embedded into someone else's page, and it is invisible to search
engines. It will inline `<svg>` instead.

The constraint that matters: **the icon names in `data/cv-*.yaml` must mean the
same thing to both renderers.** `icon: envelope` has to resolve to the Font
Awesome `envelope` glyph in the PDF and to `envelope.svg` here.

So this directory takes the SVGs of exactly the icons the data uses, copied
from the same Font Awesome release that `assets/fonts/` came from
(`fontawesome-free-7.1.0-desktop/svgs/{solid,brands}/`), and `html.py` gets a
small `name -> svg` resolver that mirrors `icons.typ`'s `icon()` / `brand()`
split:

    assets/icons/solid/envelope.svg
    assets/icons/brands/github.svg
