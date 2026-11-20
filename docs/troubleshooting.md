# Troubleshooting

[← README](../README.md) · [Getting started](getting-started.md) · [Commands](commands.md)

---

**`cv-en.yaml failed validation: at $.languages[0].level: False is not of type 'string'`**
YAML turned a bare `no` into a boolean. Quote it: `level: "no"`. The `$.…`
part is the exact path to the offending node. The [three rules that
bite](cv.md#three-rules-that-bite) cover the usual cases.

**`typst not found on PATH`**
Install it, or restart the terminal after installing so the PATH refreshes.

**`error: $CVFORGE_HOME sets the home to … which does not exist`** (or the
same from `cvforge.local.toml`)
The home is configured but not there - often OneDrive has not finished
syncing. CVForge stops rather than quietly writing into the repository. Wait
for the sync, or fix the path with `cvforge home set`.

**The letter is two pages**
Trim `sender_contacts` if the letterhead wraps, switch to `layout: compact`,
or cut a paragraph - see [cover-letters.md](cover-letters.md#layout).

**`apply` refuses: the application was already sent**
`send/` holds what the employer received and is locked once the dossier says
so. `apply --force` rebuilds it anyway - see
[applications.md](applications.md#once-it-is-sent).

**`check-clean` reports leaks in `build/` after a normal build**
Expected: a full build contains your phone number by design. `check-clean` on
its own is meant for public builds; `export` runs it on exactly the files it
publishes.

**Editing YAML in VS Code shows "Property X is not allowed" after an update**
The YAML extension caches the schema. Reload the window.

**Blank icons, the wrong typeface, `file not found (searched at /build/…)`**
See the [troubleshooting section in CLAUDE.md](../CLAUDE.md#troubleshooting) -
these come from running Typst by hand without the flags the CLI passes.
