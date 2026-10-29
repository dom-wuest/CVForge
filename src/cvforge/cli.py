"""The single entry point. `uv run cvforge <command>`.

There is deliberately no justfile: keeping the build here means one tool fewer
to install and identical behaviour on Windows, Linux and CI, with no
shell-quoting differences between PowerShell and bash.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import check as check_mod
from . import home as home_mod
from . import i18n, letter, paths, resolve, service

# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────


def cmd_resolve(args: argparse.Namespace) -> int:
    resolve.write(args.lang, args.profile)
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:
    resolve.write(args.lang, args.profile)
    service.compile_cv(args.lang)
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

        pdf = files_dir / f"cv-{lang}.pdf"
        service.compile_cv(lang, target=pdf)
        written.append(pdf)

    # The same guard that protects out/, aimed at exactly the files just
    # written - not the whole directory, which also holds unrelated PDFs.
    print()
    if check_mod.check_clean(tuple(written)) != 0:
        raise resolve.ResolveError("private data reached the export - nothing was published")

    print("\nnext: commit both repos, then cut a release in the website repo")
    print("      (it deploys on `release: published`, not on push)")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    # CVs only, deliberately. Rebuilding every application you have ever sent
    # on every `all` is wrong, and CI has no data/private.yaml to build one
    # with anyway.
    langs = [lang for lang in i18n.LANGS if paths.source(lang).is_file()]
    for lang in langs:
        print(f"[{lang}] pdf")
        cmd_pdf(argparse.Namespace(lang=lang, profile="full"))
    return 0


# ─── Cover letters ──────────────────────────────────────────────────────────


def _letter_target(slug: str, artifact: dict) -> Path:
    """Where `cvforge letter` puts the letter on its own.

    out/letters/, not the send folder: this is the draft you look at while
    writing, and `apply` owns everything in the application's send/. See
    paths.letter_pdf for why mixing the two is a way to send the wrong file.
    """
    return paths.letter_pdf(slug)


def cmd_letter(args: argparse.Namespace) -> int:
    """Build one application's cover letter, and nothing else.

    This is the fast loop while writing. `apply` is what you run when you are
    ready to send.
    """
    letter.write_letter(args.slug)
    artifact = json.loads(paths.letter_resolved(args.slug).read_text(encoding="utf-8"))
    service.compile_letter(args.slug, artifact["meta"]["lang"], _letter_target(args.slug, artifact))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """Build the send-ready folder - see service.apply_application.

    Ends with one `summary:` line in a fixed format, for whoever reads the
    output - a person or the /new-application skill.
    """
    result = service.apply_application(args.slug, force=args.force)
    print(f"\nready to send: {paths.display(result.folder)}  ({len(result.files)} files)")
    print(result.summary_line())
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    """Scaffold applications/<slug>/ - see service.new_application."""
    written = service.new_application(
        args.slug, args.lang, tailored_cv=args.cv, from_slug=args.from_slug
    )
    target = paths.application(args.slug)
    for path in written:
        print(f"  wrote {paths.display(path)}")
    for directory in ("posting", "attachments"):
        print(f"  wrote {paths.display(target / directory)}/")
    letter_file = paths.letter_source(args.slug)
    print(f"\nnext: write {paths.display(letter_file)}, then `cvforge letter {args.slug}`")
    if paths.cv_override(args.slug).is_file():
        print(f"      tailor {paths.display(paths.cv_override(args.slug))}, then `cvforge apply`")
    return 0


def cmd_dev(args: argparse.Namespace) -> int:
    """Regenerate the resolved JSON whenever the data changes.

    Typst itself is watched by Tinymist in VS Code, which gives a live preview
    with cursor-to-PDF jumping. This half only covers the data, which Tinymist
    knows nothing about. Use `--compile` if you would rather not use Tinymist.

    With `--letter <slug>` it watches that application too, and mirrors the
    resolved letter to build/letter-preview.json. Tinymist's --input flags are
    set once for the whole workspace, so the preview cannot name a slug; it
    reads the mirror, and this is what keeps the mirror current.
    """
    from watchfiles import watch

    slug = getattr(args, "letter", None)
    if slug:
        print(f"watching data/ and {paths.display(paths.application(slug))}/ (Ctrl+C to stop)")
        print("  tip: open templates/letter/main.typ and run 'Tinymist: Preview'")
    else:
        print(f"watching data/ for lang={args.lang} (Ctrl+C to stop)")
        print("  tip: open templates/pdf/main.typ and run 'Tinymist: Preview' for the live PDF")

    def rebuild() -> None:
        try:
            if slug:
                target = letter.write_letter(slug)
                paths.letter_preview().write_text(
                    target.read_text(encoding="utf-8"), encoding="utf-8"
                )
                if args.compile:
                    artifact = json.loads(target.read_text(encoding="utf-8"))
                    service.compile_letter(
                        slug, artifact["meta"]["lang"], _letter_target(slug, artifact)
                    )
            else:
                resolve.write(args.lang, args.profile)
                if args.compile:
                    service.compile_cv(args.lang)
        except resolve.ResolveError as exc:
            print(f"  error: {exc}", file=sys.stderr)

    rebuild()
    watched = [paths.DATA]
    if slug:
        watched.append(paths.application(slug))
    if args.compile:
        watched.append(paths.TEMPLATES / ("letter" if slug else "pdf"))
    for changes in watch(*watched):
        names = sorted({Path(p).name for _, p in changes})
        print(f"\nchanged: {', '.join(names)}")
        rebuild()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    home_mod.sync_schema()
    return check_mod.check()


def _clip(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def cmd_list(args: argparse.Namespace) -> int:
    """Every application, newest first - optionally only those like a new one.

    Newest first because the documents get better with every iteration: of
    two similar applications, the recent one is the better starting point.
    `--match` therefore filters but does not re-rank; the hit count is shown
    beside the date so you can weigh the two yourself.
    """
    rows = service.list_applications(args.match, args.status)
    words = len(args.match or [])
    for row in rows:
        hits = f"  [{row['hits']}/{words}]" if row["hits"] is not None else ""
        heading = _clip(f"{row['company']} · {row['title']}", 76)
        print(f"{row['date']:<10}  {row['status']:<10} {heading}")
        print(f"{'':<10}  {row['slug']}{hits}")
        if row["summary"]:
            print(f"{'':<10}  {_clip(row['summary'], 87)}")
        if row["keywords"]:
            print(f"{'':<10}  {_clip(', '.join(row['keywords']), 87)}")
        print()
    print(f"{len(rows)} application(s) in {paths.display(paths.APPLICATIONS)}")
    return 0


def cmd_home(args: argparse.Namespace) -> int:
    if args.action == "set":
        if not args.dir:
            raise resolve.ResolveError("usage: cvforge home set <dir>")
        return home_mod.set_home(args.dir)
    return home_mod.show()


def cmd_mcp_config(args: argparse.Namespace) -> int:
    """Print the claude_desktop_config.json entry for this machine.

    Printed, not written: the file is Claude Desktop's, and may hold other
    servers. The paths differ per machine (repo location, where uv lives), which
    is the whole reason this exists - the laptop runs the same command.
    """
    uv = shutil.which("uv")
    if uv is None:
        raise resolve.ResolveError("uv not found on PATH")
    entry = {
        "mcpServers": {
            "cvforge": {
                "command": uv,
                "args": ["run", "--directory", str(paths.ROOT), "--extra", "mcp", "cvforge-mcp"],
            }
        }
    }
    config = (
        Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
        if os.environ.get("APPDATA")
        else Path("~/Library/Application Support/Claude/claude_desktop_config.json").expanduser()
    )
    print(f"Merge this into {config} (Claude Desktop: Settings > Developer > Edit Config),")
    print("then restart Claude Desktop:\n")
    print(json.dumps(entry, indent=2))
    return 0


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

    # ── Cover letters ────────────────────────────────────────────────────────
    # No --profile anywhere here on purpose: a letter carries a postal address
    # by definition, so `full` is the only profile that makes sense, and a
    # letter is never exported.

    def add_slug(p: argparse.ArgumentParser) -> None:
        p.add_argument("slug", help="the directory name under applications/")

    p = sub.add_parser("new", help="scaffold a new application under applications/")
    add_slug(p)
    add_lang(p)
    p.add_argument(
        "--cv",
        action="store_true",
        help="also copy data/cv-<lang>.yaml to applications/<slug>/cv.yaml, to tailor it",
    )
    p.add_argument(
        "--from",
        dest="from_slug",
        metavar="SLUG",
        help="start letter and tailored CV from this earlier application instead",
    )
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("letter", help="build one application's cover letter")
    add_slug(p)
    p.set_defaults(func=cmd_letter)

    p = sub.add_parser("apply", help="build the send-ready folder: letter + matching CV")
    add_slug(p)
    p.add_argument(
        "--force",
        action="store_true",
        help="rebuild send/ even though the dossier says it was already sent",
    )
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("dev", help="watch data/ and regenerate the JSON")
    add_lang(p), add_profile(p)
    p.add_argument(
        "--letter",
        metavar="SLUG",
        help="watch this application instead, and mirror it to build/letter-preview.json",
    )
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

    p = sub.add_parser("list", help="every application, newest first; --match finds similar ones")
    p.add_argument(
        "--match",
        nargs="+",
        metavar="WORD",
        help="only applications whose keywords or summary contain one of these",
    )
    p.add_argument(
        "--status",
        nargs="+",
        choices=("draft", "applied", "screening", "interview", "offer", "rejected", "withdrawn"),
        help="only applications with one of these statuses",
    )
    p.set_defaults(func=cmd_list)

    p = sub.add_parser(
        "home",
        help="show where private.yaml and applications live, or `set` it for this machine",
    )
    p.add_argument("action", nargs="?", choices=("show", "set"), default="show")
    p.add_argument("dir", nargs="?", help="with `set`: the folder, e.g. one OneDrive syncs")
    p.set_defaults(func=cmd_home)

    p = sub.add_parser(
        "mcp-config",
        help="print the Claude Desktop config entry for the MCP server on this machine",
    )
    p.set_defaults(func=cmd_mcp_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        # `home` is how a broken setting gets fixed, so it is the one command
        # that runs anyway. Everything else would read or write the wrong place.
        if paths.HOME_PROBLEM and args.command != "home":
            raise resolve.ResolveError(paths.HOME_PROBLEM)
        return args.func(args)
    except resolve.ResolveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
