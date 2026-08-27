# Bundled fonts

These are committed on purpose. Typst silently falls back to a different
typeface when a font is missing, which would change the CV's appearance
depending on which machine built it. Bundling them makes the output identical
on any clone and in CI.

Every compile must pass `--font-path assets/fonts` (the `cvforge` CLI does this
for you; see `.vscode/settings.json` for the Tinymist equivalent).

| Family | Files | Version | Licence |
|---|---|---|---|
| Font Awesome 7 Free | `Font Awesome 7 Free-Solid-900.otf`, `Font Awesome 7 Free-Regular-400.otf` | 7.1.0 | SIL OFL 1.1 (fonts) — `LICENSE-FontAwesome.txt` |
| Font Awesome 7 Brands | `Font Awesome 7 Brands-Regular-400.otf` | 7.1.0 | SIL OFL 1.1 (fonts) — `LICENSE-FontAwesome.txt` |
| Inter | `Inter-{Regular,Italic,SemiBold,Bold}.otf` | 4.1 | SIL OFL 1.1 — `LICENSE-Inter.txt` |
| JetBrains Mono | `JetBrainsMono-Regular.ttf` | 2.304 | SIL OFL 1.1 — `LICENSE-JetBrainsMono.txt` |

All four are SIL Open Font License 1.1, which permits redistribution as part of
this repository. The Font Awesome bundle is dual-licensed (icons CC BY 4.0,
fonts OFL 1.1, code MIT); only the OFL-licensed font files are committed here.

## Why Font Awesome specifically

The `@preview/fontawesome` Typst package maps icon names to code points but
does **not** bundle the fonts — it renders them from the desktop OTFs. Without
these files you get `unknown font family: font awesome 7 free solid` and blank
glyphs. `templates/pdf/icons.typ` has a `FALLBACK` flag that draws stub circles
instead, for compiling without them.

## Re-downloading

```
Font Awesome  https://use.fontawesome.com/releases/v7.1.0/fontawesome-free-7.1.0-desktop.zip  → otfs/
Inter         https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip              → extras/otf/
JetBrains Mono https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/JetBrainsMono-2.304.zip → fonts/ttf/
```

Only the static instances are used — Typst's handling of variable fonts is not
relied upon here.
