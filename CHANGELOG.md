# macpmd 1.0.0 Beta 2 — 9 Mar 2026

Initial release.

## Features

- **Process management** — add, start, stop, restart, and delete processes
- **Auto-naming** — process names auto-derived from the command when `--name` is omitted
- **Batch operations** — start, stop, restart, delete, and logs accept multiple names and `--all`
- **Process listing** — view all processes with status, PID, uptime, restart count, and launchd state
- **Log management** — stdout/stderr redirected to `~/.local/share/macpmd/logs/` with automatic rotation (10 MB, 3 files)
- **Log tailing** — view recent log output or follow in real-time with `--follow`
- **Multi-process logs** — view logs for multiple processes with coloured name prefixes
- **Exit code logging** — process exit codes and signals recorded in log with `[macpmd]` prefix
- **Lifecycle logging** — process start, restart, and exit events logged automatically
- **launchd integration** — plists auto-installed on `add` for boot persistence and crash recovery
- **Sudo support** — `--sudo` flag to run processes with elevated privileges
- **Session isolation** — processes spawned in new sessions survive terminal closure
- **Coloured output** — TTY-aware ANSI colours for status display and log prefixes
- **Zero dependencies** — stdlib only, no external packages required
