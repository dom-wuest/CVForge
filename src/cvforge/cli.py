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


def _compile_pdf(lang: str) -> Path:
    """Run typst with the flags this project always needs.

    --root .            so main.typ can read /build/cv-<lang>.json by absolute path
    --font-path         so Font Awesome resolves; without it icons come out blank
                        and the body text silently falls back to another typeface
    --input lang=...    so one main.typ serves every language
    """
    target = paths.pdf(lang)
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _typst(), "compile",
        str(paths.PDF_MAIN.relative_to(paths.ROOT)),
        str(target.relative_to(paths.ROOT)),
        "--root", ".",
        "--font-path", str(paths.FONTS.relative_to(paths.ROOT)),
        "--input", f"lang={lang}",
    ]
    print("  " + " ".join(cmd[1:]))
    result = subprocess.run(cmd, cwd=paths.ROOT)
    if result.returncode != 0:
        raise resolve.ResolveError(f"typst compile failed (exit {result.returncode})")
    print(f"  wrote {target.relative_to(paths.ROOT).as_posix()}")
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


def cmd_html(args: argparse.Namespace) -> int:
    from . import html

    # The HTML target is always public. This is not a default the user can
    # override: the fragment goes on a public website.
    resolve.write(args.lang, "public")
    html.render(args.lang)
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    langs = [lang for lang in i18n.LANGS if paths.source(lang).is_file()]
    for lang in langs:
        print(f"[{lang}] pdf")
        cmd_pdf(argparse.Namespace(lang=lang, profile="full"))
    for lang in langs:
        print(f"[{lang}] html")
        cmd_html(argparse.Namespace(lang=lang))
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
        description="Data-first CV generator: one YAML source, A4 PDF and HTML fragment targets.",
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

    p = sub.add_parser("html", help="resolve (always public), then render the HTML fragment")
    add_lang(p)
    p.set_defaults(func=cmd_html)

    p = sub.add_parser("all", help="every PDF and HTML output for every language present")
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
