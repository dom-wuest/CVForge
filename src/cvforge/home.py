"""`cvforge home`: where your own data lives, and setting it once per machine.

paths.py decides the home when the package is imported; this module is the
command that shows that decision and changes it. It writes exactly two kinds
of thing: the gitignored cvforge.local.toml, and the schema mirror inside the
home. It never moves, copies or deletes your data - moving private.yaml and
the certificates is deliberately left to you (see CLAUDE.md, Guardrails).
"""

from __future__ import annotations

import os
from pathlib import Path

from . import paths, resolve


def sync_schema(home: Path | None = None, *, quiet: bool = False) -> list[Path]:
    """Bring the home's copy of schema/ up to date. Returns the files rewritten.

    Only ever writes into <home>/schema/, and only the *.json files the
    repository has - so the `$schema=../../schema/...` hint at the top of every
    application file validates against the schema of the code you are running.
    """
    mirror = paths.schema_mirror() if home is None else home / "schema"
    if mirror is None:
        return []
    mirror.mkdir(parents=True, exist_ok=True)
    written = []
    for schema in sorted(paths.SCHEMA.glob("*.json")):
        target = mirror / schema.name
        content = schema.read_bytes()
        if not target.is_file() or target.read_bytes() != content:
            target.write_bytes(content)
            written.append(target)
    if written and not quiet:
        print(f"  note: refreshed {len(written)} schema file(s) in {paths.display(mirror)}")
    return written


def _status(label: str, ok: bool, detail: str) -> None:
    print(f"  {'ok     ' if ok else 'missing'}  {label:<14} {detail}")


def show(home: Path | None = None, origin: str | None = None) -> int:
    """Print where the data lives and what is there."""
    if home is None:
        home, origin = paths.HOME, paths.HOME_SOURCE

    if home is None:
        print(f"home: the repository itself ({paths.display(paths.ROOT)})")
        print(
            "  Applications and private data stay in the working copy, gitignored. "
            "Set a synced folder with `cvforge home set <dir>`."
        )
        return 0

    print(f"home: {home}  (from {origin})")
    problem = paths.home_problem(home, origin)
    if problem:
        print(f"  error: {problem}")
        return 1

    private = home / "private.yaml"
    _status("private.yaml", private.is_file(), str(private))
    if private.is_file():
        signature = resolve.load_yaml(private).get("signature")
        if signature:
            _status("signature", (home / signature).is_file(), str(home / signature))
        else:
            _status("signature", False, "private.yaml declares no `signature`")

    applications = home / "applications"
    count = (
        sum(1 for p in applications.iterdir() if p.is_dir() and not p.name.startswith("_"))
        if applications.is_dir()
        else 0
    )
    _status("applications/", applications.is_dir(), f"{count} application(s)")

    # Left behind after a move: say so, but never touch it. Whether the copy in
    # the home is complete is yours to judge, and these files have no backup.
    legacy = [p for p in (paths.DATA / "private.yaml", paths.ASSETS / "private") if p.exists()]
    legacy_apps = [
        p.name
        for p in (paths.ROOT / "applications").iterdir()
        if p.is_dir() and not p.name.startswith("_") and not (applications / p.name).exists()
    ]
    if legacy or legacy_apps:
        print("\n  still only in the repository (copy them to the home, then delete them there):")
        for p in legacy:
            print(f"    {paths.display(p)}")
        for name in legacy_apps:
            print(f"    applications/{name}/")
    return 0


def set_home(raw: str) -> int:
    """Point this machine at a home directory. Writes cvforge.local.toml."""
    home = Path(raw).expanduser().resolve()
    if not home.is_dir():
        raise resolve.ResolveError(f"{home} is not a directory. Create it first.")
    if home == paths.ROOT or paths.ROOT in home.parents:
        # A home inside the working copy is not covered by .gitignore, so
        # private.yaml there would be one `git add .` from being committed.
        raise resolve.ResolveError(
            f"{home} is inside the repository. The home must be outside it - that is "
            f"what keeps private.yaml out of git."
        )
    if "'" in str(home):
        raise resolve.ResolveError(f"{home}: a path containing ' cannot be stored")

    paths.LOCAL_CONFIG.write_text(
        "# Written by `cvforge home set`. Per machine, gitignored.\n"
        "# Where private.yaml, private/ and applications/ live. $CVFORGE_HOME overrides it.\n"
        f"home = '{home}'\n",
        encoding="utf-8",
    )
    print(f"  wrote {paths.display(paths.LOCAL_CONFIG)}")

    applications = home / "applications"
    if not applications.is_dir():
        applications.mkdir()
        print(f"  wrote {applications}/")
    sync_schema(home)

    env = os.environ.get(paths.HOME_ENV, "").strip()
    if env and Path(env).expanduser().resolve() != home:
        print(f"  note: ${paths.HOME_ENV} is set to {env} and takes precedence in this shell")

    print()
    return show(home, paths.LOCAL_CONFIG.name)
