"""PreToolUse hook: refuse anything that would overwrite, move or delete private files.

data/private.yaml and assets/private/ are gitignored and exist nowhere else. They
have been lost once already - a test ran `cp data/private.example.yaml
data/private.yaml`, a cleanup ran `rm -rf data/private.yaml assets/private` - and
the signature scan had to be redone. CLAUDE.md says never to do that; this makes
the harness enforce it, in every session, not only when the rule is remembered.

Reading stays allowed: `cat`, `grep`, the Read tool. Blocked:

- Write / Edit / MultiEdit / NotebookEdit on a protected path.
- A shell command that names a protected path together with a verb that writes,
  moves or deletes, or that redirects output onto one.
- A shell command that deletes the directories containing them (`rm -rf data`),
  or `git clean` with -x/-X, which deletes ignored files.

Deliberately conservative: a false positive costs one manual command, a false
negative costs a certificate. Exit 2 blocks the call and shows stderr to Claude.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROTECTED = ("data/private.yaml", "assets/private")

# A protected path as it may appear in a command: / or \ separators, optional
# ./ or a leading absolute prefix. Not private.example.yaml.
NAMED = re.compile(r"data[/\\]+private\.yaml\b|assets[/\\]+private\b", re.IGNORECASE)

WRITE_VERBS = re.compile(
    r"\b(rm|rmdir|mv|cp|del|erase|rd|move|copy|xcopy|robocopy|unlink|shred|truncate|tee"
    r"|dd|install|rsync|ln|sed\s+-i|perl\s+-i|chmod|chown"
    r"|Remove-Item|Move-Item|Copy-Item|Rename-Item|Set-Content|Add-Content|Clear-Content"
    r"|Out-File|New-Item|ri|mi|ci)\b",
    re.IGNORECASE,
)

# Output redirected onto a protected path: `> data/private.yaml`, `>> "assets/private/x"`.
REDIRECT = re.compile(
    r">{1,2}\s*[\"']?[^\s\"'|;&]*(data[/\\]+private\.yaml|assets[/\\]+private)", re.IGNORECASE
)

# Deleting a parent directory takes the private files with it.
DELETE_PARENT = re.compile(
    r"\b(rm|rmdir|rd|del|Remove-Item|ri)\b[^|;&\n]*?\s[\"']?(\./|\.\\)?(data|assets)[/\\]?[\"']?(\s|$|;|&|\|)",
    re.IGNORECASE,
)

GIT_CLEAN_IGNORED = re.compile(r"\bgit\s+clean\b[^|;&\n]*\s-[a-wyzA-WYZ]*[xX]", re.IGNORECASE)

REASON = (
    "Blocked by .claude/hooks/protect_private.py: data/private.yaml and assets/private/ "
    "are gitignored and have no copy anywhere (see CLAUDE.md, Guardrails). Reading them "
    "is fine; writing, moving or deleting is not. If this change is really wanted, ask "
    "the user to make it by hand."
)


def _is_protected(path_str: str, cwd: str) -> bool:
    path = Path(path_str)
    if not path.is_absolute():
        path = Path(cwd) / path
    text = path.resolve().as_posix().lower()
    return any(text.endswith("/" + p) or ("/" + p + "/") in text for p in PROTECTED)


def _command_hits(command: str) -> str | None:
    if REDIRECT.search(command):
        return "redirects output onto a protected path"
    if NAMED.search(command) and WRITE_VERBS.search(command):
        return "names a protected path together with a write/move/delete command"
    if DELETE_PARENT.search(command):
        return "deletes a directory that contains private files"
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
