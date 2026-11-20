# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools>=4.50"]
# ///
"""Build the README's overview diagram, one SVG per GitHub theme.

    uv run docs/images/overview.py

Writes overview-light.svg and overview-dark.svg next to this script; README.md
picks one with <picture>. Edit this file, never the SVGs.

Text is outlined from the committed fonts, as in assets/logo/build.py, because
an SVG shown as an <img> cannot load a font: outlined, it renders identically
on every machine. The palette follows the logo's. Every box names the doc in
docs/ that explains it - keep those names in step when a doc is renamed.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "assets" / "fonts"

FACES = {
    "regular": "Inter-Regular.otf",
    "semibold": "Inter-SemiBold.otf",
    "bold": "Inter-Bold.otf",
    "mono": "JetBrainsMono-Regular.ttf",
}

LIGHT = dict(
    ink="#1C1C22",
    muted="#59636E",
    faint="#818B98",
    line="#D1D9E0",
    box="#FFFFFF",
    tint="#F6F8FA",
    ember="#E8590C",
    ember_tint="#FFF4E6",
    ember_line="#F4A26B",
)
DARK = dict(
    ink="#E6EDF3",
    muted="#9198A1",
    faint="#6E7681",
    line="#3D444D",
    box="#151B23",
    tint="#151B23",
    ember="#F76707",
    ember_tint="#221810",
    ember_line="#9A4A1C",
)


@cache
def font(face: str):
    f = TTFont(FONTS / FACES[face])
    return f, f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm


def width(text: str, size: float, face: str, tracking: float = 0) -> float:
    f, glyphs, cmap, upm = font(face)
    return sum(glyphs[cmap[ord(c)]].width for c in text) * size / upm + tracking * size * len(text)


# Every glyph used is outlined once, in font units, into <defs>; text is a run
# of <use> references to it. Outlining each occurrence instead made each SVG
# five times the size.
DEFS: dict[str, str] = {}


def glyph(face: str, char: str) -> str:
    gid = f"{face[0]}{ord(char):x}"
    if gid not in DEFS:
        _, glyphs, cmap, _ = font(face)
        pen = SVGPathPen(glyphs, ntos=lambda v: str(round(v)))
        glyphs[cmap[ord(char)]].draw(pen)
        DEFS[gid] = f'<path id="{gid}" d="{pen.getCommands()}"/>'
    return gid


def text(s, x, y, size, face="regular", cls="ink", anchor="start", tracking=0.0) -> str:
    _, glyphs, cmap, upm = font(face)
    w = width(s, size, face, tracking)
    x = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
    scale = size / upm
    uses, advance = [], 0.0  # in font units
    for c in s:
        if not c.isspace():
            uses.append(f'<use href="#{glyph(face, c)}" x="{advance:.0f}"/>')
        advance += glyphs[cmap[ord(c)]].width + tracking * upm
    return (
        f'<g class="t-{cls}" transform="translate({x:.1f} {y:.1f}) scale({scale:.5f} '
        f'{-scale:.5f})">{"".join(uses)}</g>'
    )


def box(x, y, w, h, private=False, r=8) -> str:
    cls = "b-priv" if private else "b-pub"
    return f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/>'


def card(x, y, w, h, title, mono, desc, doc, private=False) -> str:
    out = [box(x, y, w, h, private)]
    out.append(text(title, x + 14, y + 25, 14.5, "semibold"))
    out.append(text(doc, x + w - 12, y + 24, 10, "mono", "faint", "end"))
    if mono:
        out.append(text(mono, x + 14, y + 44, 10.5, "mono", "ember" if private else "muted"))
    for i, line in enumerate(desc):
        out.append(text(line, x + 14, y + (62 if mono else 44) + i * 16, 11.5, "regular", "muted"))
    return "".join(out)


def arrow(x1, y1, x2, y2, private=False) -> str:
    mx = (x1 + x2) / 2
    kind = "priv" if private else "pub"
    head = f"M{x2 - 7} {y2 - 4}L{x2} {y2}L{x2 - 7} {y2 + 4}z"
    return (
        f'<path class="a-{kind}" d="M{x1} {y1}C{mx} {y1} {mx} {y2} {x2 - 5} {y2}"/>'
        f'<path class="h-{kind}" d="{head}"/>'
    )


def heading(s, x, y) -> str:
    return text(s, x, y, 10.5, "bold", "faint", tracking=0.08)


def style(c) -> str:
    return (
        f".t-ink{{fill:{c['ink']}}}.t-muted{{fill:{c['muted']}}}.t-faint{{fill:{c['faint']}}}"
        f".t-ember{{fill:{c['ember']}}}"
        f".b-pub{{fill:{c['box']};stroke:{c['line']};stroke-width:1.2}}"
        f".b-priv{{fill:{c['ember_tint']};stroke:{c['ember_line']};stroke-width:1.2;"
        f"stroke-dasharray:5 3}}"
        f".b-core{{fill:{c['tint']};stroke:{c['ink']};stroke-width:1.6}}"
        f".a-pub{{fill:none;stroke:{c['ink']};stroke-width:1.5}}"
        f".a-priv{{fill:none;stroke:{c['ember']};stroke-width:1.5;stroke-dasharray:4 3}}"
        f".h-pub{{fill:{c['ink']}}}.h-priv{{fill:{c['ember']}}}"
        f".rule{{stroke:{c['line']};stroke-width:1}}"
        f".chip-pub{{fill:none;stroke:{c['ink']};stroke-width:1.2}}"
        f".chip-priv{{fill:none;stroke:{c['ember']};stroke-width:1.2}}"
    )


def diagram(c) -> str:
    W, H = 900, 544
    s = []
    # ── columns ──
    C1, C2, C3 = 20, 320, 616
    W1, W2, W3 = 236, 236, 264
    s += [
        heading("YOU WRITE", C1, 24),
        heading("CVFORGE BUILDS", C2, 24),
        heading("YOU GET", C3, 24),
    ]

    inputs = [
        (
            "CV data",
            "data/cv-en.yaml · cv-de.yaml",
            ["Experience, skills, projects.", "German and English."],
            "cv.md",
            False,
        ),
        (
            "Private data",
            "<home>/private.yaml",
            ["Phone, street, signature,", "certificates. Never in git."],
            "private-data.md",
            True,
        ),
        (
            "Applications",
            "<home>/applications/<slug>/",
            ["Letter, tailored CV, posting,", "people, timeline."],
            "applications.md",
            True,
        ),
    ]
    ih, istep = 96, 116
    for i, (t, m, d, doc, p) in enumerate(inputs):
        s.append(card(C1, 44 + i * istep, W1, ih, t, m, d, doc, p))

    outputs = [
        ("CV as PDF", "A4, Typst, DE + EN", "cv.md", True),
        ("The website", "public data + PDFs", "website.md", False),
        ("Cover letter", "DIN 5008, one page", "cover-letters.md", True),
        ("Send-ready folder", "letter, CV, attachments", "applications.md", True),
        ("Dashboard", "all applications", "tracking.md", True),
    ]
    oh, ostep = 58, 70
    for i, (t, m, doc, p) in enumerate(outputs):
        y = 44 + i * ostep
        s.append(box(C3, y, W3, oh, p))
        s.append(text(t, C3 + 14, y + 24, 14.5, "semibold"))
        s.append(text(m, C3 + 14, y + 43, 11.5, "regular", "muted"))
        s.append(text(doc, C3 + W3 - 12, y + 43, 10, "mono", "faint", "end"))

    # ── the core ──
    cy, ch = 70, 238
    s.append(f'<rect class="b-core" x="{C2}" y="{cy}" width="{W2}" height="{ch}" rx="10"/>')
    s.append(text("resolve", C2 + 18, cy + 30, 17, "bold"))
    steps = ["validate against the schema", "merge private data", "derive every display string"]
    for i, st in enumerate(steps):
        y = cy + 58 + i * 22
        s.append(f'<circle class="h-pub" cx="{C2 + 24}" cy="{y - 4}" r="2.5"/>')
        s.append(text(st, C2 + 36, y, 12, "regular", "ink"))
    s.append(
        f'<line class="rule" x1="{C2 + 18}" y1="{cy + 132}" x2="{C2 + W2 - 18}" y2="{cy + 132}"/>'
    )
    s.append(text("two profiles", C2 + 18, cy + 154, 10.5, "bold", "faint", tracking=0.08))
    # chips
    fx, py = C2 + 18, cy + 166
    fw = width("public", 12, "semibold") + 20
    s.append(f'<rect class="chip-priv" x="{fx}" y="{py}" width="{fw}" height="24" rx="12"/>')
    s.append(text("full", fx + fw / 2, py + 16.5, 12, "semibold", "ember", "middle"))
    s.append(text("CV PDFs, letters", fx + fw + 8, py + 16.5, 11.5, "regular", "muted"))
    px, py = C2 + 18, py + 32
    pw = fw = max(fw, width("public", 12, "semibold") + 20)
    s.append(f'<rect class="chip-pub" x="{px}" y="{py}" width="{pw}" height="24" rx="12"/>')
    s.append(text("public", px + pw / 2, py + 16.5, 12, "semibold", "ink", "middle"))
    s.append(text("the website", px + pw + 8, py + 16.5, 11.5, "regular", "muted"))

    # check box below the core
    ky = cy + ch + 16
    s.append(box(C2, ky, W2, 50))
    s.append(text("check · leak scan", C2 + 18, ky + 22, 13, "semibold"))
    s.append(
        text(
            "export refuses if a private value matches", C2 + 18, ky + 39, 10.5, "regular", "muted"
        )
    )

    # ── arrows ──
    ends_in = [cy + 70, cy + 120, cy + 170]
    for i, (_, _, _, _, p) in enumerate(inputs):
        s.append(arrow(C1 + W1, 44 + i * istep + ih / 2, C2, ends_in[i], p))
    starts_out = [cy + 50, cy + 85, cy + 120, cy + 155, cy + 190]
    for i, (_, _, _, p) in enumerate(outputs):
        s.append(arrow(C2 + W2, starts_out[i], C3, 44 + i * ostep + oh / 2, p))

    # ── interfaces ──
    by = 420
    s.append(heading("DRIVE IT FROM", C1, by - 12))
    pills = [
        ("Command line", "cvforge pdf · apply · list", "commands.md"),
        ("VS Code", "tasks · live preview", "getting-started.md"),
        ("Claude Code", "/new-application", "with-claude.md"),
        ("Claude Desktop", "local MCP server", "with-claude.md"),
    ]
    gap = 14
    pw_ = (W - 2 * C1 - 3 * gap) / 4
    for i, (t, m, doc) in enumerate(pills):
        x = C1 + i * (pw_ + gap)
        s.append(box(x, by, pw_, 78))
        s.append(text(t, x + 14, by + 25, 14, "semibold"))
        s.append(text(m, x + 14, by + 44, 10.5, "mono", "muted"))
        s.append(text(doc, x + 14, by + 63, 10, "mono", "faint"))

    # ── legend ──
    ly = H - 12
    s.append(box(C1, ly - 11, 22, 14, False, 3))
    s.append(text("public — in git, on the website", C1 + 30, ly, 11.5, "regular", "muted"))
    lx = C1 + 30 + width("public — in git, on the website", 11.5, "regular") + 26
    s.append(box(lx, ly - 11, 22, 14, True, 3))
    s.append(text("holds private data — never in git", lx + 30, ly, 11.5, "regular", "muted"))

    # Every text() call above has added its glyphs to DEFS by now.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-label="CVForge overview: CV data, private data and applications are '
        f'resolved into a CV PDF, the website, cover letters, a send-ready folder and a dashboard">'
        f"<title>What CVForge does</title><style>{style(c)}</style>"
        f"<defs>{''.join(DEFS.values())}</defs>{''.join(s)}</svg>\n"
    )


def main() -> None:
    for name, c in (("overview-light.svg", LIGHT), ("overview-dark.svg", DARK)):
        svg = diagram(c)
        (HERE / name).write_text(svg, encoding="utf-8")
        print(f"  wrote docs/images/{name}  ({len(svg) // 1024 + 1} KB)")


if __name__ == "__main__":
    main()
