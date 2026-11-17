# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools>=4.50"]
# ///
"""Build CVForge's logo files from one geometry and the committed Inter Bold.

    uv run assets/logo/build.py

Writes, next to this script:

    cvforge-header-light.svg  the README header - mark and wordmark, animated -
    cvforge-header-dark.svg   one per GitHub theme, picked by <picture> in README.md
    cvforge-mark.svg          the mark alone, static, follows the colour scheme
    cvforge-favicon.svg       the mark simplified for 16-32 px: no lines, no sparks

The mark is "the strike": a hammer meets a page, sparks fly, the page's lines
are written. The wordmark is outlined from assets/fonts/Inter-Bold.otf because
an SVG shown as an image - a README, a favicon - cannot load a font.

Colours are CSS custom properties with fallbacks (`var(--cvf-ink, #1C1C22)`),
so a page that inlines the mark - the dashboard - recolours it to its own
theme, and every class and keyframe is prefixed `cvf-` so an inlined copy
cannot collide with the page's CSS. The dashboard animates the same classes on
hover; keep the class names when changing the geometry.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONT = HERE.parent / "fonts" / "Inter-Bold.otf"

LIGHT = {
    "ink": "#1C1C22",
    "paper": "#FFFFFF",
    "ember": "#E8590C",
    "spark": "#F59F00",
    "flash": "#FFE1C7",
}
# GitHub's dark theme: text #E6EDF3 on #0D1117; the page is a raised surface.
DARK = {
    "ink": "#E6EDF3",
    "paper": "#21262D",
    "ember": "#F76707",
    "spark": "#F59F00",
    "flash": "#5A2E14",
}

# ─── The mark, on a 64-unit grid ────────────────────────────────────────────
PAGE = "M26 26h20l10 10v22H26z"
FOLD = "M46 26v10h10"
LINES = ("M32 41h14", "M32 47h18", "M32 53h10")
SPARKS = "M38 15l4-4M40 21l6-2M35 10l1-5"
# The hammer is drawn upright around its head's centre and turned onto the
# page; the swing pivots on the end of the handle (the bottom of its box).
HAMMER = "translate(20 13) rotate(45)"


def mark(*, simple: bool = False) -> str:
    if simple:
        # Favicon: fewer, heavier shapes - lines and sparks are mush at 16 px.
        return (
            f'<path class="cvf-paper" d="{PAGE}"/>'
            f'<path class="cvf-line" style="stroke-width:5" d="{PAGE}"/>'
            f'<g transform="{HAMMER}"><rect class="cvf-ink" x="-12" y="-7" width="24" '
            f'height="14" rx="2"/><rect class="cvf-ink" x="-3.5" y="6" width="7" '
            f'height="18" rx="3"/></g>'
        )
    lines = "".join(
        f'<path class="cvf-text cvf-l{i}" pathLength="1" d="{d}"/>' for i, d in enumerate(LINES, 1)
    )
    return (
        f'<path class="cvf-paper cvf-page" d="{PAGE}"/>'
        f'<path class="cvf-line" d="{PAGE} {FOLD}"/>'
        f"{lines}"
        f'<g transform="{HAMMER}"><g class="cvf-swing">'
        f'<rect class="cvf-ink" x="-11" y="-6" width="22" height="12" rx="2"/>'
        f'<rect class="cvf-ink" x="-2.5" y="6" width="5" height="18" rx="2.5"/>'
        f"</g></g>"
        f'<path class="cvf-spark cvf-sparks" d="{SPARKS}"/>'
    )


def palette(c: dict[str, str]) -> str:
    return (
        f".cvf-ink{{fill:var(--cvf-ink,{c['ink']})}}"
        f".cvf-paper{{fill:var(--cvf-paper,{c['paper']})}}"
        f".cvf-ember{{fill:var(--cvf-ember,{c['ember']})}}"
        f".cvf-line{{fill:none;stroke:var(--cvf-ink,{c['ink']});stroke-width:3;"
        f"stroke-linejoin:round;stroke-linecap:round}}"
        f".cvf-text{{fill:none;stroke:var(--cvf-ember,{c['ember']});stroke-width:3;"
        f"stroke-linecap:round}}"
        f".cvf-spark{{fill:none;stroke:var(--cvf-spark,{c['spark']});stroke-width:2.5;"
        f"stroke-linecap:round}}"
    )


def adaptive() -> str:
    return palette(LIGHT) + f"@media (prefers-color-scheme:dark){{{palette(DARK)}}}"


def strike(c: dict[str, str], seconds: float = 3.2) -> str:
    """The loop: lift, strike, sparks and a flash of heat, the lines are written,
    rest. Reduced motion shows the resting frame, which is the static mark."""
    run = f"{seconds}s infinite both"
    lines = "".join(
        f".cvf-l{i}{{stroke-dasharray:1;animation:cvf-l{i} {run} ease-out}}"
        f"@keyframes cvf-l{i}{{0%,{a}%{{stroke-dashoffset:1}}{a + 10}%,90%"
        f"{{stroke-dashoffset:0}}98%,100%{{stroke-dashoffset:1}}}}"
        for i, a in ((1, 38), (2, 44), (3, 50))
    )
    return (
        f".cvf-swing{{transform-box:fill-box;transform-origin:50% 100%;"
        f"animation:cvf-swing {run} cubic-bezier(.55,0,.45,1)}}"
        f"@keyframes cvf-swing{{0%{{transform:rotate(-26deg)}}26%{{transform:rotate(-30deg)}}"
        f"35%{{transform:rotate(3deg)}}39%,72%{{transform:rotate(0deg)}}"
        f"100%{{transform:rotate(-26deg)}}}}"
        f".cvf-sparks{{transform-box:fill-box;transform-origin:0% 100%;"
        f"animation:cvf-sparks {run} ease-out}}"
        f"@keyframes cvf-sparks{{0%,34%{{opacity:0;transform:scale(.4)}}"
        f"38%{{opacity:1;transform:scale(.95)}}58%,100%{{opacity:0;transform:scale(1.6)}}}}"
        f".cvf-page{{animation:cvf-flash {run} ease-out}}"
        f"@keyframes cvf-flash{{0%,34%{{fill:{c['paper']}}}38%{{fill:{c['flash']}}}"
        f"62%,100%{{fill:{c['paper']}}}}}"
        f"{lines}"
        f"@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}"
    )


# ─── The wordmark, outlined from Inter Bold ─────────────────────────────────


def outline(
    text: str, size: float, x: float, baseline: float, tracking: float
) -> tuple[str, float]:
    """`text` as one SVG path at `size` units, starting at `x`. Returns (d, x after)."""
    font = TTFont(FONT)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    for char in text:
        glyph = glyphs[cmap[ord(char)]]
        glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        x += glyph.width * scale + tracking * size
    return pen.getCommands(), x


def x_height(size: float) -> float:
    font = TTFont(FONT)
    return font["OS/2"].sxHeight / font["head"].unitsPerEm * size


def header(c: dict[str, str]) -> str:
    # Room on the left and top for the lifted hammer, which swings outside
    # the 64-unit mark.
    left, top, size, gap, tracking = 10, 6, 36, 12, -0.03
    baseline = top + 35 + x_height(size) / 2  # x-height centred on the page
    start = left + 58 + gap
    cv, x = outline("cv", size, start, baseline, tracking)
    forge, x = outline("forge", size, x, baseline, tracking)
    width, height = round(x + 6), 70
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width * 2}" height="{height * 2}" role="img" aria-label="CVForge">'
        f"<title>CVForge</title><style>{palette(c)}{strike(c)}</style>"
        f'<g transform="translate({left} {top})">{mark()}</g>'
        f'<path class="cvf-ink" d="{cv}"/><path class="cvf-ember" d="{forge}"/></svg>\n'
    )


def standalone(body: str, label: str, size: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" '
        f'height="{size}" role="img" aria-label="{label}"><title>{label}</title>'
        f"<style>{adaptive()}</style>{body}</svg>\n"
    )


def main() -> None:
    files = {
        "cvforge-header-light.svg": header(LIGHT),
        "cvforge-header-dark.svg": header(DARK),
        "cvforge-mark.svg": standalone(mark(), "CVForge", 64),
        "cvforge-favicon.svg": standalone(mark(simple=True), "CVForge", 32),
    }
    for name, svg in files.items():
        (HERE / name).write_text(svg, encoding="utf-8")
        print(f"  wrote assets/logo/{name}  ({len(svg) // 1024 + 1} KB)")


if __name__ == "__main__":
    main()
