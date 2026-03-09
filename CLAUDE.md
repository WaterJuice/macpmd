# CLAUDE.md

This file provides guidance for AI agents working on this project.

## Project Overview

macpmd is a macOS process manager — a PM2 equivalent that uses launchd for persistence and crash recovery. It provides a CLI (using a custom argbuilder, not click) for adding, starting, stopping, restarting, listing, and monitoring processes. Processes are spawned in new sessions so they survive terminal closure. Adding a process automatically starts it and installs a launchd plist for boot persistence and crash recovery.

## Language and Spelling

Use **Australian English** throughout:
- colour (not color)
- initialise (not initialize)
- sanitise (not sanitize)
- organisation (not organization)

## Code Style

### Python Files

Every Python file should have:
1. A file header block with description and version history
2. Section headers separating major sections (Imports, Constants, Functions, etc.)
3. Horizontal separators (92 chars of `-`) above each function definition

Example structure:
```python
# ----------------------------------------------------------------------------------------
#   filename.py
#   -----------
#
#   Brief description of what this module does.
#
#   (c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
#
#   Version History
#   ---------------
#   Mar 2026 - Created
# ----------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------------------------

import sys

# ----------------------------------------------------------------------------------------
#   Functions
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def my_function() -> None:
    """Docstring here."""
    pass
```

### General

- Python 3.12+ (do **not** use `from __future__ import annotations`)
- Use type hints throughout
- Prefer pathlib.Path over os.path
- Single-line imports, no blank lines between import groups (configured in pyproject.toml)
- Run `make format` to auto-fix import ordering
- Zero external dependencies — stdlib only
- CLI uses argbuilder.py (custom argparse wrapper), not click or argparse directly

## Common Commands

```bash
make help       # Show all available targets
make check      # Run ruff + pyright
make format     # Auto-fix and format code
make build      # Build wheel + docs into output/
make docs       # Build HTML documentation into html/
make clean      # Remove build artefacts
make dev        # Just create dev (.venv) setup
```

## Project Structure

```
macpmd/
├-- __init__.py       # Package init, exports __version__
├-- __main__.py       # Entry point for python -m macpmd
├-- version.py        # Version string handling
├-- argbuilder.py     # Custom argparse wrapper (from cal-publish-python)
├-- cli.py            # CLI commands and argument parsing
├-- colour.py         # ANSI colour output (TTY-aware)
├-- state.py          # Process state persistence (~/.local/share/macpmd/state.json)
├-- logs.py           # Log file management with rotation and tailing
├-- process.py        # Process spawning and lifecycle management
└-- launchd.py        # launchd plist generation and management
```

## Architecture

### Process Management
- Processes are spawned via `subprocess.Popen` with `start_new_session=True`
- stdout/stderr are redirected to `~/.local/share/macpmd/logs/<name>.log`
- State is persisted in `~/.local/share/macpmd/state.json`
- Stopping sends SIGTERM to the process group, then SIGKILL after 3 seconds
- Commands are wrapped in a shell snippet that logs start/exit events to stdout (the log file)
- Process lifecycle events (start, restart, exit) are logged with `[macpmd]` prefix

### launchd Integration
- Adding a process automatically installs a launchd plist
- Stopping a process uninstalls its plist first (prevents launchd restarting it)
- Restarting uninstalls plist, restarts, then reinstalls plist
- Plists are installed in `~/Library/LaunchAgents/`
- Plists use `KeepAlive: true` for crash recovery and `RunAtLoad: true` for boot persistence
- Label format: `com.macpmd.<name>`

### CLI Commands
- `add` — register and start a new process (supports optional `--name` and `--sudo`)
- `start` — start existing stopped/errored processes (supports multiple names and `--all`)
- `stop` — stop one or more processes (supports multiple names and `--all`)
- `restart` — restart one or more processes (supports multiple names and `--all`)
- `delete` — remove one or more processes (supports multiple names and `--all`)
- `list` — show all processes in a table
- `logs` — view logs (supports multiple names, `--all`, `--follow`, `--lines`)

### Log Management
- Logs rotate at 10 MB, up to 3 rotated files kept
- `tail_log` reads across all rotated files
- `--lines 0` shows all log history
- Multiple process logs are prefixed with coloured process names
- `--follow` shows recent lines before switching to live mode

## Key Design Decisions

1. **argbuilder for CLI** — custom argparse wrapper, zero dependencies.
2. **Shell execution** — commands run via `shell=True` for user convenience (pipes, env vars, etc.).
3. **Session isolation** — `start_new_session=True` so processes survive terminal closure.
4. **launchd for persistence** — native macOS approach for boot persistence and crash recovery.
5. **Auto-install plists** — no separate `startup` command; plists installed on `add`.
6. **Simple state file** — JSON in ~/.local/share/macpmd/ for easy debugging and manual inspection.
7. **Shell wrapper for lifecycle logging** — commands wrapped with printf to log start/exit events, works for both macpmd and launchd restarts.

## Testing Changes

After making changes:
1. Run `make check` to verify linting and types pass
2. Run `make build` to verify the full build works
3. Test with `uv run macpmd list` to verify the CLI works

## Versioning

- Version is derived from git tags via uv-dynamic-versioning
- Create a tag like `1.0.0` before running `make build` for a release (no `v` prefix)
- The build generates `_version.py` at build time, which is not committed
- If no tags exist, version falls back to "dev"

## Commits

When committing:
- Use clear, descriptive commit messages
- Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` in commits made with AI assistance
- **Never rewrite git history** unless explicitly asked to

## Licence

Released under the [Unlicense](https://unlicense.org/) — public domain.
