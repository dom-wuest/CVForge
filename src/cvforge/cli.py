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
from datetime import date
from pathlib import Path

from . import check as check_mod
from . import home as home_mod
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


def _compile_pdf(lang: str, target: Path | None = None, artifact: Path | None = None) -> int | None:
    """Compile the CV. Returns the page count.

    `target` defaults to out/cv-<lang>.pdf. `export` passes a path in the
    website's working copy instead, so the public PDF never lands in out/ and
    overwrites the full-profile one you send with applications.

    `artifact` is a resolved CV other than build/cv-<lang>.json - an
    application's tailored copy. main.typ reads it by root-absolute path.
    """
    target = paths.pdf(lang) if target is None else target
    inputs = {"lang": lang}
    if artifact is not None:
        inputs["artifact"] = "/" + artifact.relative_to(paths.ROOT).as_posix()
    return _compile(paths.CV_MAIN, target, inputs)


def _compile_letter(slug: str, lang: str, target: Path) -> int | None:
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
    return pages


def _expected_cv_pages(cv: dict) -> int:
    """How many pages a CV that has not overflowed comes out at.

    One, plus the projects page when `projects_layout: page` gives projects one
    of their own. More than this means the main page overflowed - the symptom
    is a stub of the sidebar rule on the next page.
    """
    return 2 if cv["meta"].get("projects_layout") == "page" else 1


def _pages(count: int | None) -> str:
    if count is None:
        return "? pages"
    return f"{count} page{'s' if count != 1 else ''}"


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

        pdf = files_dir / f"cv-{lang}.pdf"
        _compile_pdf(lang, target=pdf)
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
    prevent. Only ever the one application's send/ folder, which nothing but
    `apply` writes to, and only the files directly in it - never a directory,
    never anything beside it.
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
    _compile_letter(args.slug, artifact["meta"]["lang"], _letter_target(args.slug, artifact))
    return 0


def _sent_on(slug: str) -> str | None:
    """Why the dossier says this application went out, or None if it did not."""
    dossier_file = paths.dossier(slug)
    if not dossier_file.is_file():
        return None
    dossier = resolve.load_yaml(dossier_file)
    if dossier.get("applied"):
        return f"applied {dossier['applied']}"
    if dossier.get("status") in check_mod.SENT:
        return f"status {dossier['status']}"
    return None


def cmd_apply(args: argparse.Namespace) -> int:
    """Build the whole send-ready folder: letter, CV, and every attachment.

    The CV is rebuilt here rather than reused from out/ so the two documents in
    the folder are guaranteed to be the same vintage, and in the same language
    as the letter. Both are profile=full - this folder is for an employer, not
    for the web.

    The CV is the one the letter's sender block came from (`meta.cv_source`):
    the application's tailored cv.yaml if it has one, else data/cv-<lang>.yaml.
    A tailored CV resolves to its own build/cv-app-<slug>.json, never over the
    base CV's artifact.

    Ends with one `summary:` line in a fixed format, for whoever reads the
    output - a person or the /new-application skill.

    Refuses, unless --force, once the dossier says the application went out:
    send/ is then the record of what the employer received, and a rebuild
    would replace it with what the sources produce today.
    """
    sent = _sent_on(args.slug)
    if sent and not args.force:
        raise resolve.ResolveError(
            f"{args.slug} was sent ({sent}), so {paths.display(paths.bundle(args.slug))} "
            f"holds what the employer received. Rebuilding would replace it.\n"
            f"  Use `cvforge letter {args.slug}` to look at a draft, or `apply --force` "
            f"if you really mean to rebuild the folder."
        )

    letter.write_letter(args.slug)
    artifact = json.loads(paths.letter_resolved(args.slug).read_text(encoding="utf-8"))
    lang = artifact["meta"]["lang"]
    labels = artifact["labels"]
    stem = _slugify_name(artifact["meta"]["name"])
    attached = artifact.get("attachments", [])
    # The same decision the letter's sender block was resolved from a moment
    # ago (`meta.cv_source` records it). Asked again rather than parsed back
    # out of the artifact, because a tailored CV in the home is an absolute
    # path there, not a repo-relative one.
    cv_source = paths.cv_source(lang, args.slug)
    tailored = cv_source != paths.source(lang)

    # Refuse before writing anything. A folder with a hole in it is worse than
    # no folder at all: the point of this command is that you can send what it
    # produced without checking it first. Every problem at once, so fixing them
    # is one round trip rather than five.
    unresolved = [a["label"] for a in attached if not a.get("file")]
    if unresolved:
        raise resolve.ResolveError(
            "these attachments have no file, so the folder was not built: "
            + ", ".join(unresolved)
            + f"\n  Check `documents:` in {letter.PRIVATE_NAME}, and that each `file:` exists."
        )

    out = paths.bundle(args.slug)
    _clear_bundle(out)

    print(f"[{args.slug}] letter")
    letter_pages = _compile_letter(
        args.slug, lang, out / _send_name(1, stem, labels["file_letter"], ".pdf")
    )

    print(f"[{args.slug}] cv ({lang}, {paths.display(cv_source)})")
    cv_json = resolve.write(
        lang,
        "full",
        quiet=True,
        source=cv_source,
        target=paths.cv_resolved_for(args.slug) if tailored else None,
    )
    cv_pages = _compile_pdf(
        lang,
        target=out / _send_name(2, stem, labels["file_cv"], ".pdf"),
        artifact=cv_json if tailored else None,
    )
    expected = _expected_cv_pages(json.loads(cv_json.read_text(encoding="utf-8")))
    if cv_pages is not None and cv_pages != expected:
        print(
            f"  warning: the CV is {_pages(cv_pages)}, expected {expected} - it overflowed. "
            f"Shorten {paths.display(cv_source)}, or see 'Fitting on one page' in CLAUDE.md.",
            file=sys.stderr,
        )

    if attached:
        print(f"[{args.slug}] attachments")
        for i, entry in enumerate(attached, start=3):
            source = Path(entry["file"])
            target = out / _send_name(i, stem, entry["label"], source.suffix.lower())
            shutil.copyfile(source, target)
            print(f"  wrote {paths.display(target)}")

    print(f"\nready to send: {paths.display(out)}  ({2 + len(attached)} files)")
    print(
        f"summary: letter {_pages(letter_pages)} | "
        f"cv {_pages(cv_pages)} (expected {expected}) | "
        f"cv source {paths.display(cv_source)} | "
        f"{len(attached)} attachment{'s' if len(attached) != 1 else ''}"
    )
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    """Scaffold applications/<slug>/ from applications/_template/."""
    target = paths.application(args.slug)
    if target.exists():
        raise resolve.ResolveError(f"{paths.display(target)} already exists")
    if not paths.APPLICATION_TEMPLATE.is_dir():
        raise resolve.ResolveError(f"missing scaffold: {paths.display(paths.APPLICATION_TEMPLATE)}")
    base = paths.source(args.lang)
    if args.cv and not base.is_file():
        raise resolve.ResolveError(f"--cv: {paths.display(base)} does not exist")

    target.mkdir(parents=True)
    written: list[Path] = []
    # The `$schema=../../schema/` hints below resolve against this in a home.
    home_mod.sync_schema()

    source = (paths.APPLICATION_TEMPLATE / "letter.yaml").read_text(encoding="utf-8")
    source = source.replace("slug: new-application", f"slug: {args.slug}")
    source = source.replace("lang: de", f"lang: {args.lang}")
    letter_file = paths.letter_source(args.slug)
    letter_file.write_text(source, encoding="utf-8")
    written.append(letter_file)

    # dossier.yaml is gitignored; the example it comes from is not.
    example = paths.APPLICATION_TEMPLATE / "dossier.example.yaml"
    if example.is_file():
        # The one fact known now: the day it was started. `cvforge list` falls
        # back to it for an application that has not been sent yet.
        created = f'timeline:\n  - date: "{date.today().isoformat()}"\n    event: "Created"\n'
        text = re.sub(
            r"^timeline: \[\].*\n",
            created,
            example.read_text(encoding="utf-8"),
            count=1,
            flags=re.MULTILINE,
        )
        dossier_file = paths.dossier(args.slug)
        dossier_file.write_text(text, encoding="utf-8")
        written.append(dossier_file)

    # A CV tailored to this application: a full copy, so it is a snapshot of
    # what was sent and later edits to the base CV do not reach back into it.
    # The base CV also feeds the website, which is why tailoring happens here.
    if args.cv:
        text = base.read_text(encoding="utf-8")
        # One directory deeper than data/, so the schema hint needs one more ../
        text = text.replace("$schema=../schema/", "$schema=../../schema/", 1)
        header = (
            f"# Tailored copy of {paths.display(base)}, taken {date.today().isoformat()}.\n"
            f"# For this application alone: `cvforge letter` and `apply` use it\n"
            f"# instead of the base CV, and edits here never reach the website.\n"
            f"# private.yaml is still merged in, exactly as for the base CV.\n"
        )
        first, _, rest = text.partition("\n")
        if first.startswith("# yaml-language-server:"):
            text = f"{first}\n#\n{header}{rest}"
        else:
            text = header + text
        cv_file = paths.cv_override(args.slug)
        cv_file.write_text(text, encoding="utf-8")
        written.append(cv_file)

    # Both gitignored: the archived posting, and any work sample you send to
    # this company alone.
    (target / "posting").mkdir()
    paths.attachments(args.slug).mkdir()

    for path in written:
        print(f"  wrote {paths.display(path)}")
    for directory in ("posting", "attachments"):
        print(f"  wrote {paths.display(target / directory)}/")
    print(f"\nnext: write {paths.display(letter_file)}, then `cvforge letter {args.slug}`")
    if args.cv:
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
    home_mod.sync_schema()
    return check_mod.check()


def _application_date(slug: str, dossier: dict) -> str:
    """When this application happened, for sorting: sent, else started.

    `applied` if it was sent; else the first timeline entry, which `new`
    writes on the day it was created; else the slug's YYYY-MM prefix.
    """
    if dossier.get("applied"):
        return dossier["applied"]
    timeline = dossier.get("timeline") or []
    if timeline and timeline[0].get("date"):
        return timeline[0]["date"]
    prefix = re.match(r"\d{4}-\d{2}", slug)
    return prefix.group(0) if prefix else ""


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
    if not paths.APPLICATIONS.is_dir():
        print(f"no applications in {paths.display(paths.APPLICATIONS)}")
        return 0

    words = [w.casefold() for w in args.match or []]
    rows = []
    for directory in sorted(p for p in paths.APPLICATIONS.iterdir() if p.is_dir()):
        slug = directory.name
        if slug.startswith("_"):
            continue
        dossier_file, letter_file = paths.dossier(slug), paths.letter_source(slug)
        dossier = resolve.load_yaml(dossier_file) if dossier_file.is_file() else {}
        letter_data = resolve.load_yaml(letter_file) if letter_file.is_file() else {}

        status = dossier.get("status") or "?"
        if args.status and status not in args.status:
            continue

        title = (letter_data.get("job") or {}).get("title") or (dossier.get("role") or {}).get(
            "title", ""
        )
        company = (dossier.get("company") or {}).get("name") or (
            letter_data.get("recipient") or {}
        ).get("company", "")
        summary = dossier.get("summary") or ""
        keywords = dossier.get("keywords") or []

        hits = ""
        if words:
            # Not the job title: an unwritten letter still carries the
            # scaffold's "Rendering Engineer", and would match on it.
            haystack = " ".join([summary, *keywords]).casefold()
            found = sum(1 for w in words if w in haystack)
            if not found:
                continue
            hits = f"  [{found}/{len(words)}]"

        when = _application_date(slug, dossier)
        rows.append((when, slug, status, company, title, summary, hits, keywords))

    rows.sort(key=lambda r: r[0], reverse=True)
    for when, slug, status, company, title, summary, hits, keywords in rows:
        print(f"{when:<10}  {status:<10} {_clip(f'{company} · {title}', 76)}")
        print(f"{'':<10}  {slug}{hits}")
        if summary:
            print(f"{'':<10}  {_clip(summary, 87)}")
        if keywords:
            print(f"{'':<10}  {_clip(', '.join(keywords), 87)}")
        print()
    print(f"{len(rows)} application(s) in {paths.display(paths.APPLICATIONS)}")
    return 0


def cmd_home(args: argparse.Namespace) -> int:
    if args.action == "set":
        if not args.dir:
            raise resolve.ResolveError("usage: cvforge home set <dir>")
        return home_mod.set_home(args.dir)
    return home_mod.show()


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
