"""The single entry point. `uv run cvforge <command>`.

There is deliberately no justfile: keeping the build here means one tool fewer
to install and identical behaviour on Windows, Linux and CI, with no
shell-quoting differences between PowerShell and bash.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import check as check_mod
from . import i18n, paths, resolve


def _typst() -> str:
    exe = shutil.which("typst")
    if exe is None:
        raise resolve.ResolveError(
            "typst not found on PATH. Install it from https://github.com/typst/typst/releases "
            "or `winget install Typst.Typst`."
        )
    return exe


def _page_count(pdf: Path) -> int | None:
    """Page count of a PDF we just produced, or None if it cannot be read.

    One page is a design requirement here, and the German CV has only a few
    millimetres of slack, so a silent regression to two pages is easy to ship
    unnoticed. This reads /Count out of the page tree rather than taking on a
    PDF dependency.

    It only ever parses our own Typst output, which writes the page tree as
    "<</Type/Pages/Count 1/Kids[...]>>". Anything else returns None and the
    caller simply omits the number - this must never fail a build. The search
    is anchored on /Type/Pages because /Count also appears in the outline.
    """
    try:
        blob = pdf.read_bytes()
    except OSError:
        return None
    marker = blob.find(b"/Type/Pages")
    if marker == -1:
        return None
    key = blob.find(b"/Count", marker)
    if key == -1 or key - marker > 200:
        return None
    digits = bytearray()
    for byte in blob[key + 6 : key + 32]:
        if 48 <= byte <= 57:
            digits.append(byte)
        elif digits:
            break
    return int(digits) if digits else None


def _compile_pdf(lang: str, target: Path | None = None) -> Path:
    """Run typst with the flags this project always needs.

    --root .            so main.typ can read /build/cv-<lang>.json by absolute path
    --font-path         so Font Awesome resolves; without it icons come out blank
                        and the body text silently falls back to another typeface
    --input lang=...    so one main.typ serves every language

    `target` defaults to out/cv-<lang>.pdf. `export` passes a path in the
    website's working copy instead, so the public PDF never lands in out/ and
    overwrites the full-profile one you send with applications. --root only
    constrains what Typst may *read*, so an output outside the repo is fine.
    """
    target = paths.pdf(lang) if target is None else target
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_arg = str(target.relative_to(paths.ROOT))
    except ValueError:
        out_arg = str(target)
    cmd = [
        _typst(),
        "compile",
        str(paths.PDF_MAIN.relative_to(paths.ROOT)),
        out_arg,
        "--root",
        ".",
        "--font-path",
        str(paths.FONTS.relative_to(paths.ROOT)),
        "--input",
        f"lang={lang}",
    ]
    print("  " + " ".join(cmd[1:]))
    result = subprocess.run(cmd, cwd=paths.ROOT)
    if result.returncode != 0:
        raise resolve.ResolveError(f"typst compile failed (exit {result.returncode})")
    pages = _page_count(target)
    suffix = "" if pages is None else f"  ({pages} page{'s' if pages != 1 else ''})"
    print(f"  wrote {paths.display(target)}{suffix}")
    return target


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────


def cmd_resolve(args: argparse.Namespace) -> int:
    resolve.write(args.lang, args.profile)
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:
    resolve.write(args.lang, args.profile)
    _compile_pdf(args.lang)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Write the website's copy of the CV into its working tree.

    A local file copy rather than a fetch, which is what keeps this working
    while CVForge is private: no deploy key, no token in a public repository's
    secrets, nothing to expire. The site only deploys on a published release
    anyway, so there is no continuous-delivery benefit being given up.
    """
    site = Path(args.to).expanduser().resolve()
    if not (site / "config" / "_default" / "hugo.yaml").is_file():
        raise resolve.ResolveError(
            f"{site} does not look like the Hugo site: no config/_default/hugo.yaml.\n"
            "       Point --to at the Portfolio repository root."
        )

    data_dir = site / "data" / "cv"
    files_dir = site / "static" / "files"
    data_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    langs = [lang for lang in i18n.LANGS if paths.source(lang).is_file()]
    written: list[Path] = []
    for lang in langs:
        # public, and not overridable. This writes into a public repository.
        resolve.write(lang, "public", quiet=True)

        # Read back what was actually written rather than trusting the call
        # above. This is the guarantee the PDF rests on: a literal grep cannot
        # see inside a compressed PDF, but the PDF is rendered from exactly
        # this artifact, so a public artifact is a public PDF.
        artifact = resolve.load_resolved(lang)
        if artifact["meta"]["profile"] != "public":
            raise resolve.ResolveError(
                f"build/cv-{lang}.json is profile="
                f"{artifact['meta']['profile']!r} - refusing to export"
            )

        target = data_dir / f"{lang}.json"
        shutil.copyfile(paths.resolved(lang), target)
        print(f"  wrote {paths.display(target)}  (profile=public)")
        written.append(target)

        written.append(_compile_pdf(lang, target=files_dir / f"cv-{lang}.pdf"))

    # The same guard that protects out/, aimed at exactly the files just
    # written - not the whole directory, which also holds unrelated PDFs.
    print()
    if check_mod.check_clean(tuple(written)) != 0:
        raise resolve.ResolveError("private data reached the export - nothing was published")

    print("\nnext: commit both repos, then cut a release in the website repo")
    print("      (it deploys on `release: published`, not on push)")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    langs = [lang for lang in i18n.LANGS if paths.source(lang).is_file()]
    for lang in langs:
        print(f"[{lang}] pdf")
        cmd_pdf(argparse.Namespace(lang=lang, profile="full"))
    return 0


def cmd_dev(args: argparse.Namespace) -> int:
    """Regenerate build/cv-<lang>.json whenever the data changes.

    Typst itself is watched by Tinymist in VS Code, which gives a live preview
    with cursor-to-PDF jumping. This half only covers the data, which Tinymist
    knows nothing about. Use `--compile` if you would rather not use Tinymist.
    """
    from watchfiles import watch

    print(f"watching data/ for lang={args.lang} (Ctrl+C to stop)")
    print("  tip: open templates/pdf/main.typ and run 'Tinymist: Preview' for the live PDF")

    def rebuild() -> None:
        try:
            resolve.write(args.lang, args.profile)
            if args.compile:
                _compile_pdf(args.lang)
        except resolve.ResolveError as exc:
            print(f"  error: {exc}", file=sys.stderr)

    rebuild()
    watched = [paths.DATA]
    if args.compile:
        watched.append(paths.TEMPLATES / "pdf")
    for changes in watch(*watched):
        names = sorted({Path(p).name for _, p in changes})
        print(f"\nchanged: {', '.join(names)}")
        rebuild()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    return check_mod.check()


def cmd_check_clean(args: argparse.Namespace) -> int:
    return check_mod.check_clean()


# ─────────────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cvforge",
        description="Data-first CV generator: one YAML source, an A4 PDF and the website's data.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_lang(p: argparse.ArgumentParser) -> None:
        p.add_argument("--lang", default="en", choices=i18n.LANGS, help="default: en")

    def add_profile(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--profile",
            default="full",
            choices=resolve.PROFILES,
            help="full merges data/private.yaml (default); public ignores it entirely",
        )

    p = sub.add_parser("resolve", help="YAML -> build/cv-<lang>.json")
    add_lang(p), add_profile(p)
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("pdf", help="resolve, then compile the A4 PDF")
    add_lang(p), add_profile(p)
    p.set_defaults(func=cmd_pdf)

    p = sub.add_parser(
        "export",
        help="write the public CV data and PDFs into the website's working copy",
    )
    p.add_argument(
        "--to",
        required=True,
        metavar="PATH",
        help="the Hugo site's repository root, e.g. ../Website/Portfolio",
    )
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("all", help="the PDF for every language present")
    p.set_defaults(func=cmd_all)

    p = sub.add_parser("dev", help="watch data/ and regenerate the JSON")
    add_lang(p), add_profile(p)
    p.add_argument(
        "--compile",
        action="store_true",
        help="also run typst on every change (unnecessary if you use Tinymist)",
    )
    p.set_defaults(func=cmd_dev)

    p = sub.add_parser("check", help="validate the data and report content warnings")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("check-clean", help="fail if a private value reached build/ or out/")
    p.set_defaults(func=cmd_check_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except resolve.ResolveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
