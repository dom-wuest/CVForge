"""HTML renderer - SCAFFOLD.

Wired end to end and producing valid output, but deliberately minimal: the
markup is real and semantic, the styling is not. See the TODOs in
templates/web/cv.css and templates/web/cv.html.j2.

Contract (fixed now, so the eventual implementation cannot drift):

  * Output is a FRAGMENT - no <html>, <head> or <body>. It is dropped into an
    existing page on dom-wuest.de, plus a separate out/cv.css.
  * Everything is namespaced under `.cvf`, every custom property is `--cvf-`
    prefixed. It must not collide with the host site's stylesheet.
  * Real markup: <section> per section, <h2> headings, <ol> for timelines,
    <time datetime="2021-10"> for dates. This is the version search engines
    read.
  * No JavaScript.

The theme is NOT shared with templates/pdf/theme.typ. Web is scroll, not A4,
and cv.css is meant to be restyled against the host site. The two only have to
cover the same data.
"""

from __future__ import annotations

from typing import Any

from . import paths, resolve


class ProfileError(resolve.ResolveError):
    """Refused to render private data to a public target."""


def render(lang: str) -> None:
    """Render out/cv-<lang>.html and out/cv.css from build/cv-<lang>.json."""
    data = resolve.load_resolved(lang)
    _assert_public(data)

    import jinja2

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(paths.WEB_TEMPLATES),
        autoescape=jinja2.select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    fragment = env.get_template("cv.html.j2").render(cv=data, labels=data["labels"])

    paths.OUT.mkdir(parents=True, exist_ok=True)
    target = paths.html(lang)
    target.write_text(fragment, encoding="utf-8")

    css_target = paths.OUT / "cv.css"
    css_target.write_text(
        (paths.WEB_TEMPLATES / "cv.css").read_text(encoding="utf-8"), encoding="utf-8"
    )

    print(f"  wrote {target.relative_to(paths.ROOT).as_posix()}")
    print(f"  wrote {css_target.relative_to(paths.ROOT).as_posix()}")


def _assert_public(data: dict[str, Any]) -> None:
    """The hard guarantee, not a convention.

    `resolve` stamps the profile into the artifact. Anything other than
    "public" means private values may be present, and this target publishes to
    a website, so refuse rather than warn.
    """
    profile = data.get("meta", {}).get("profile")
    if profile != "public":
        raise ProfileError(
            f"refusing to render HTML from a profile={profile!r} artifact. "
            f"Re-run `cvforge resolve --profile public` first."
        )

    leaked = [c["id"] for c in data.get("contacts", []) if c.get("private") == "hidden"]
    if leaked:
        raise ProfileError("resolved artifact still contains hidden contacts: " + ", ".join(leaked))


# TODO(html): inline <svg> icons instead of the Font Awesome webfont.
#   A webfont is a poor fit for a fragment embedded in someone else's page and
#   is invisible to search engines. The icon *names* in the YAML must keep
#   meaning the same thing in both renderers, so this needs a name -> svg
#   resolver mirroring the icon()/brand() split in templates/pdf/icons.typ.
#   See assets/icons/README.md.
def icon_svg(name: str, *, brand: bool = False) -> str:
    return ""
