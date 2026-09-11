"""The single entry point. `uv run cvforge <command>`.

There is deliberately no justfile: keeping the build here means one tool fewer
to install and identical behaviour on Windows, Linux and CI, with no
shell-quoting differences between PowerShell and bash.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

from . import check as check_mod
from . import i18n, letter, paths, resolve


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
    is anchored on the /Pages type because /Count also appears in the outline.

    The whitespace in the pattern is not decorative: PDF allows a space between
    a key and its value, and typst 0.14 emits "/Type /Pages" where 0.13 emitted
    "/Type/Pages". Matching only the tight form made this return None on every
    build - which is invisible, because None just omits the number.
    """
    try:
        blob = pdf.read_bytes()
    except OSError:
        return None
    found = re.search(rb"/Type\s*/Pages\b", blob)
    if found is None:
        return None
    key = re.compile(rb"/Count\s*(\d+)").search(blob, found.end(), found.end() + 200)
    return int(key.group(1)) if key else None


def _compile(main: Path, target: Path, inputs: dict[str, str]) -> int | None:
    """Run typst with the flags this project always needs. Returns the page count.

    --root .            so a template can read /build/<artifact>.json by absolute path
    --font-path         so Font Awesome resolves; without it icons come out blank
                        and the body text silently falls back to another typeface
    --input k=v         so one template serves every language, and every letter

    --root only constrains what Typst may *read*, so an output outside the repo
    is fine - that is how `export` writes into the website's working copy.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_arg = str(target.relative_to(paths.ROOT))
    except ValueError:
        out_arg = str(target)
    cmd = [
        _typst(),
        "compile",
        str(main.relative_to(paths.ROOT)),
        out_arg,
        "--root",
        ".",
        "--font-path",
        str(paths.FONTS.relative_to(paths.ROOT)),
    ]
    for key, value in inputs.items():
        cmd += ["--input", f"{key}={value}"]

    print("  " + " ".join(cmd[1:]))
    result = subprocess.run(cmd, cwd=paths.ROOT)
    if result.returncode != 0:
        raise resolve.ResolveError(f"typst compile failed (exit {result.returncode})")

    pages = _page_count(target)
    suffix = "" if pages is None else f"  ({pages} page{'s' if pages != 1 else ''})"
    print(f"  wrote {paths.display(target)}{suffix}")
    return pages


def _compile_pdf(lang: str, target: Path | None = None) -> Path:
    """Compile the CV.

    `target` defaults to out/cv-<lang>.pdf. `export` passes a path in the
    website's working copy instead, so the public PDF never lands in out/ and
    overwrites the full-profile one you send with applications.
    """
    target = paths.pdf(lang) if target is None else target
    _compile(paths.CV_MAIN, target, {"lang": lang})
    return target


def _compile_letter(slug: str, lang: str, target: Path) -> Path:
    """Compile one cover letter, and complain if it did not come out on one page.

    A two-page cover letter is a content problem, not a layout one - nobody
    reads the second page - so this is loud but not fatal: you may well be
    mid-edit, and failing the build would only get in the way.
    """
    pages = _compile(paths.LETTER_MAIN, target, {"slug": slug, "lang": lang})
    if pages is not None and pages > 1:
        print(
            f"  warning: the letter is {pages} pages. A cover letter is one page - "
            f"cut a paragraph, or trim `sender_contacts` if the letterhead is "
            f"crowding the address field.",
            file=sys.stderr,
        )
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
    # CVs only, deliberately. Rebuilding every application you have ever sent
    # on every `all` is wrong, and CI has no data/private.yaml to build one
    # with anyway.
    langs = [lang for lang in i18n.LANGS if paths.source(lang).is_file()]
    for lang in langs:
        print(f"[{lang}] pdf")
        cmd_pdf(argparse.Namespace(lang=lang, profile="full"))
    return 0


# ─── Cover letters ──────────────────────────────────────────────────────────


def _slugify_name(name: str) -> str:
    """A person's name as a filename an employer's system will not mangle.

    "Dominik Wüst" -> "Dominik_Wuest". Transliterating rather than stripping,
    because "Wst" is worse than either.
    """
    folded = name
    for source, target in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        folded = folded.replace(source, target).replace(source.upper(), target.capitalize())
    # Apostrophes vanish rather than becoming separators: a document label like
    # "Bachelor's Degree Certificate" should read Bachelors_Degree_Certificate,
    # not Bachelor_s_Degree_Certificate.
    folded = folded.replace("'", "").replace("’", "")
    ascii_only = unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", ascii_only).strip("_")


def _send_name(index: int, stem: str, label: str, suffix: str) -> str:
    """One file in the send-ready folder: "01_Dominik_Wuest_Anschreiben.pdf".

    The numeric prefix is what makes the folder sort in the order the letter
    lists things, in every file dialog and every upload form. Alphabetical
    order only matches what an employer expects by luck - "Arbeitszeugnis"
    sorts before "Anschreiben".
    """
    return f"{index:02d}_{stem}_{_slugify_name(label)}{suffix}"


def _clear_bundle(out: Path) -> None:
    """Empty the send folder before refilling it.

    Without this, dropping an attachment from the letter leaves the old file
    behind and you send it anyway - the exact failure this command exists to
    prevent. Only ever the one slug's directory, which nothing but `apply`
    writes to, under out/, which is generated and gitignored.
    """
    if not out.is_dir():
        return
    stale = [p for p in out.iterdir() if p.is_file()]
    for path in stale:
        path.unlink()
    if stale:
        print(f"  cleared {len(stale)} stale file(s) from {paths.display(out)}")


def _letter_target(slug: str, artifact: dict) -> Path:
    """Where `cvforge letter` puts the letter on its own.

    out/letters/, not the send folder: this is the draft you look at while
    writing, and `apply` owns everything in out/applications/<slug>/. See
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
    _compile_letter(args.slug, artifact["meta"]["lang"], _letter_target(args.slug, artifact))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """Build the whole send-ready folder: letter, CV, and every attachment.

    The CV is rebuilt here rather than reused from out/ so the two documents in
    the folder are guaranteed to be the same vintage, and in the same language
    as the letter. Both are profile=full - this folder is for an employer, not
    for the web.
    """
    letter.write_letter(args.slug)
    artifact = json.loads(paths.letter_resolved(args.slug).read_text(encoding="utf-8"))
    lang = artifact["meta"]["lang"]
    labels = artifact["labels"]
    stem = _slugify_name(artifact["meta"]["name"])
    attached = artifact.get("attachments", [])

    # Refuse before writing anything. A folder with a hole in it is worse than
    # no folder at all: the point of this command is that you can send what it
    # produced without checking it first. Every problem at once, so fixing them
    # is one round trip rather than five.
    unresolved = [a["label"] for a in attached if not a.get("file")]
    if unresolved:
        raise resolve.ResolveError(
            "these attachments have no file, so the folder was not built: "
            + ", ".join(unresolved)
            + "\n  Check `documents:` in data/private.yaml, and that each `file:` exists."
        )

    out = paths.bundle(args.slug)
    _clear_bundle(out)

    print(f"[{args.slug}] letter")
    _compile_letter(args.slug, lang, out / _send_name(1, stem, labels["file_letter"], ".pdf"))

    print(f"[{args.slug}] cv ({lang})")
    resolve.write(lang, "full", quiet=True)
    _compile_pdf(lang, target=out / _send_name(2, stem, labels["file_cv"], ".pdf"))

    if attached:
        print(f"[{args.slug}] attachments")
        for i, entry in enumerate(attached, start=3):
            source = Path(entry["file"])
            target = out / _send_name(i, stem, entry["label"], source.suffix.lower())
            shutil.copyfile(source, target)
            print(f"  wrote {paths.display(target)}")

    print(f"\nready to send: {paths.display(out)}  ({2 + len(attached)} files)")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    """Scaffold applications/<slug>/ from applications/_template/."""
    target = paths.application(args.slug)
    if target.exists():
        raise resolve.ResolveError(f"{paths.display(target)} already exists")
    if not paths.APPLICATION_TEMPLATE.is_dir():
        raise resolve.ResolveError(f"missing scaffold: {paths.display(paths.APPLICATION_TEMPLATE)}")

    target.mkdir(parents=True)
    written: list[Path] = []

    source = (paths.APPLICATION_TEMPLATE / "letter.yaml").read_text(encoding="utf-8")
    source = source.replace("slug: new-application", f"slug: {args.slug}")
    source = source.replace("lang: de", f"lang: {args.lang}")
    letter_file = paths.letter_source(args.slug)
    letter_file.write_text(source, encoding="utf-8")
    written.append(letter_file)

    # dossier.yaml is gitignored; the example it comes from is not.
    example = paths.APPLICATION_TEMPLATE / "dossier.example.yaml"
    if example.is_file():
        dossier_file = paths.dossier(args.slug)
        dossier_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(dossier_file)

    # Both gitignored: the archived posting, and any work sample you send to
    # this company alone.
    (target / "posting").mkdir()
    paths.attachments(args.slug).mkdir()

    for path in written:
        print(f"  wrote {paths.display(path)}")
    for directory in ("posting", "attachments"):
        print(f"  wrote {paths.display(target / directory)}/")
    print(f"\nnext: write {paths.display(letter_file)}, then `cvforge letter {args.slug}`")
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
        print(f"watching data/ and applications/{slug}/ (Ctrl+C to stop)")
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
                    _compile_letter(slug, artifact["meta"]["lang"], _letter_target(slug, artifact))
            else:
                resolve.write(args.lang, args.profile)
                if args.compile:
                    _compile_pdf(args.lang)
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

    # ── Cover letters ────────────────────────────────────────────────────────
    # No --profile anywhere here on purpose: a letter carries a postal address
    # by definition, so `full` is the only profile that makes sense, and a
    # letter is never exported.

    def add_slug(p: argparse.ArgumentParser) -> None:
        p.add_argument("slug", help="the directory name under applications/")

    p = sub.add_parser("new", help="scaffold a new application under applications/")
    add_slug(p)
    add_lang(p)
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("letter", help="build one application's cover letter")
    add_slug(p)
    p.set_defaults(func=cmd_letter)

    p = sub.add_parser("apply", help="build the send-ready folder: letter + matching CV")
    add_slug(p)
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
