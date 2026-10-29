"""PreToolUse hook: refuse anything that would overwrite, move or delete private files.

private.yaml and the private/ folder - data/private.yaml and assets/private/ in
the repository, or <home>/private.yaml and <home>/private/ once a home is set
(`cvforge home set`) - exist nowhere else that a mistake cannot reach. They
have been lost once already - a test ran `cp data/private.example.yaml
data/private.yaml`, a cleanup ran `rm -rf data/private.yaml assets/private` -
and the signature scan had to be redone. CLAUDE.md says never to do that; this
makes the harness enforce it, in every session, not only when the rule is
remembered.

Reading stays allowed: `cat`, `grep`, the Read tool. Blocked:

- Write / Edit / MultiEdit / NotebookEdit on a protected path.
- A shell command that names a protected path together with a verb that writes,
  moves or deletes, or that redirects output onto one.
- A shell command that deletes the directories containing them (`rm -rf data`,
  the home, or the home's applications/), or `git clean` with -x/-X, which
  deletes ignored files.

Deliberately conservative: a false positive costs one manual command, a false
negative costs a certificate. Exit 2 blocks the call and shows stderr to Claude.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTECTED = ("data/private.yaml", "assets/private")


def _home() -> Path | None:
    """The configured home, read the way src/cvforge/paths.py reads it.

    Duplicated rather than imported: the hook must work with whatever `python`
    is on PATH, without the project's environment.
    """
    raw = os.environ.get("CVFORGE_HOME", "").strip()
    config = ROOT / "cvforge.local.toml"
    if not raw and config.is_file():
        found = re.search(r"^\s*home\s*=\s*'([^']*)'\s*$", config.read_text("utf-8"), re.M)
        raw = found.group(1).strip() if found else ""
    return Path(raw).expanduser() if raw else None


HOME = _home()

# A protected path as it may appear in a command: / or \ separators, any
# prefix. private.yaml anywhere (not private.example.yaml), and a directory
# called private - assets/private, <home>/private - as a path component.
NAMED = re.compile(
    r"\bprivate\.yaml\b|[/\\]private(?![\w.-])|\bprivate[/\\]",
    re.IGNORECASE,
)

WRITE_VERBS = re.compile(
    r"\b(rm|rmdir|mv|cp|del|erase|rd|move|copy|xcopy|robocopy|unlink|shred|truncate|tee"
    r"|dd|install|rsync|ln|sed\s+-i|perl\s+-i|chmod|chown"
    r"|Remove-Item|Move-Item|Copy-Item|Rename-Item|Set-Content|Add-Content|Clear-Content"
    r"|Out-File|New-Item|ri|mi|ci)\b",
    re.IGNORECASE,
)

DELETE_VERBS = r"\b(rm|rmdir|rd|del|erase|mv|move|Remove-Item|Move-Item|ri|mi)\b"

# Output redirected onto a protected path: `> data/private.yaml`, `>> "assets/private/x"`.
REDIRECT = re.compile(
    r">{1,2}\s*[\"']?[^\s\"'|;&]*(private\.yaml|[/\\]private(?![\w.-])|\bprivate[/\\])",
    re.IGNORECASE,
)

# Deleting a parent directory takes the private files with it. In the home,
# applications/ is as irreplaceable as private/ - an archived posting is gone
# once the employer takes it down - so the whole of it counts.
DELETE_PARENT = re.compile(
    r"\b(rm|rmdir|rd|del|Remove-Item|ri)\b[^|;&\n]*?\s[\"']?(\./|\.\\)?(data|assets|private)"
    r"[/\\]?[\"']?(\s|$|;|&|\|)",
    re.IGNORECASE,
)

GIT_CLEAN_IGNORED = re.compile(r"\bgit\s+clean\b[^|;&\n]*\s-[a-wyzA-WYZ]*[xX]", re.IGNORECASE)

REASON = (
    "Blocked by .claude/hooks/protect_private.py: private.yaml and the private/ folder "
    "(in the repository or in the home) and the home's applications/ have no copy that a "
    "mistake cannot reach (see CLAUDE.md, Guardrails). Reading them is fine; writing, "
    "moving or deleting is not. If this change is really wanted, ask the user to make it "
    "by hand."
)


def _spellings(path: Path) -> list[str]:
    """How a path may be written in a command: C:\\x, C:/x, /c/x (Git Bash)."""
    text = str(path)
    forms = {text, text.replace("\\", "/")}
    if len(text) > 1 and text[1] == ":":
        forms.add("/" + text[0].lower() + text[2:].replace("\\", "/"))
    return sorted(forms, key=len, reverse=True)


def _deletes_home(command: str) -> bool:
    """A delete or move naming the home itself or its applications/ as a whole."""
    if HOME is None or not re.search(DELETE_VERBS, command, re.IGNORECASE):
        return False
    for form in _spellings(HOME):
        parts = [re.escape(p) for p in re.split(r"[/\\]+", form)]
        whole = r"[/\\]+".join(parts) + r"([/\\]+applications)?[/\\]*[\"']?(\s|$|;|&|\|)"
        if re.search(whole, command, re.IGNORECASE):
            return True
    return False


def _is_protected(path_str: str, cwd: str) -> bool:
    path = Path(path_str)
    if not path.is_absolute():
        path = Path(cwd) / path
    text = path.resolve().as_posix().lower()
    if any(text.endswith("/" + p) or ("/" + p + "/") in text for p in PROTECTED):
        return True
    if HOME is not None:
        home = HOME.resolve().as_posix().lower()
        if text == home + "/private.yaml" or text.startswith(home + "/private/"):
            return True
    return False


def _command_hits(command: str) -> str | None:
    if REDIRECT.search(command):
        return "redirects output onto a protected path"
    if NAMED.search(command) and WRITE_VERBS.search(command):
        return "names a protected path together with a write/move/delete command"
    if DELETE_PARENT.search(command):
        return "deletes a directory that contains private files"
    if _deletes_home(command):
        return "deletes or moves the home, or its applications/"
    if GIT_CLEAN_IGNORED.search(command):
        return "git clean -x/-X deletes ignored files, which include the private ones"
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # not ours to judge; never break the session on bad input

    tool = event.get("tool_name", "")
    params = event.get("tool_input") or {}
    cwd = event.get("cwd") or "."

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        target = params.get("file_path") or params.get("notebook_path") or ""
        if target and _is_protected(target, cwd):
            print(f"{REASON}\n(target: {target})", file=sys.stderr)
            return 2
    elif tool in ("Bash", "PowerShell"):
        why = _command_hits(params.get("command") or "")
        if why:
            print(f"{REASON}\n(the command {why})", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
