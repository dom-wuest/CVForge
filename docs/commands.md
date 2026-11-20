# Commands

[← README](../README.md) · [Getting started](getting-started.md) · [CV](cv.md) · [Private data](private-data.md) · [Cover letters](cover-letters.md) · [Applications](applications.md) · [Tracking](tracking.md) · [Website](website.md) · [Claude](with-claude.md) · **Commands**

---

Everything goes through one CLI, `uv run cvforge <command>`. In VS Code the
common ones are also under **Tasks: Run Task**. `uv run cvforge <command> -h`
prints the options of each.

## The CV

| Command | Does |
|---|---|
| `pdf [--lang en] [--profile full]` | Build `out/cv-<lang>.pdf` and print its page count. `--profile public` leaves `private.yaml` out. |
| `all` | The CV in every language. |
| `resolve [--lang en] [--profile full]` | Only the data step: write `build/cv-<lang>.json`, the input the template reads. |
| `dev [--lang en] [--compile]` | Regenerate the data on every save, for the [live preview](getting-started.md#live-preview). |
| `check` | Validate every CV, letter and dossier; report content warnings. |
| `export --to <site>` | Publish the public CV to the website repository - see [website.md](website.md). |
| `check-clean` | Fail if a value from `private.yaml` is in `build/` or `out/`. After a normal (full) build it will find your phone number there - that is expected; it is meant for public builds. |

## Applications

| Command | Does |
|---|---|
| `new <slug> [--lang de] [--cv] [--from <slug>]` | Scaffold an application. `--cv` adds a tailored CV copy, `--from` starts from an earlier application. |
| `letter <slug>` | Build the cover letter as a draft → `out/letters/<slug>.pdf`. |
| `apply <slug> [--force]` | Build the send-ready folder: letter, CV, attachments. Refuses once sent unless `--force`. |
| `dev --letter <slug>` | Live-preview loop for a letter. |
| `list [--match WORD …] [--status …]` | Every application, newest first; `--match` finds ones like a new posting. |
| `dashboard [--open]` | Write `<home>/dashboard.html` - see [tracking.md](tracking.md#the-dashboard). |

See [applications.md](applications.md) and [cover-letters.md](cover-letters.md).

## Setup

| Command | Does |
|---|---|
| `home` | Show where private data and applications live, and what is missing. |
| `home set <dir>` | Set the home for this machine - see [private-data.md](private-data.md#the-home). |
| `mcp-config` | Print the Claude Desktop entry for the MCP server - see [with-claude.md](with-claude.md). |

## Output conventions

Every command prints `  wrote <path>  (…)` for each file it writes, with the
page count for PDFs, and `  note: …` for anything informational. A mistake in
your data is reported as one line starting with `error:` and the exact place,
such as `at $.languages[0].level` - never as a traceback.
