# macpmd 1.0.0 Beta 5 — 15 Mar 2026

## Linux Support

- **systemd backend** — macpmd now supports Linux via systemd user services and system services
- **Service backend abstraction** — platform-specific service managers are selected automatically (launchd on macOS, systemd on Linux)
- **Linux service files** — systemd units installed in `~/.config/systemd/user/` (standard) or `/etc/systemd/system/` (sudo) with `Restart=always` for crash recovery
- **TCC checks are macOS-only** — TCC path validation is now skipped on Linux where it does not apply

# macpmd 1.0.0 Beta 4 — 10 Mar 2026

Initial release.

## Features

- **Process management** — add, start, stop, restart, and delete processes
- **Auto-naming** — process names auto-derived from the command when `--name` is omitted
- **Batch operations** — start, stop, restart, delete, info, and logs accept multiple names and `--all`
- **Process listing** — view all processes with status, PID, uptime, restart count, sudo, and service state
- **Process info** — `info` command shows detailed information including the full command and working directory; supports `--json` output
- **Log management** — stdout/stderr redirected to `~/.local/share/macpmd/logs/` with automatic rotation (10 MB, 3 files)
- **Log tailing** — view recent log output or follow in real-time with `--follow`
- **Multi-process logs** — view logs for multiple processes with coloured name prefixes
- **Exit code logging** — process exit codes and signals recorded in log with `[macpmd]` prefix
- **Lifecycle logging** — process start, restart, and exit events logged automatically
- **Immediate failure detection** — processes that exit immediately on `add` are reported as errors and not persisted
- **launchd integration** — plists auto-installed on `add` for boot persistence and crash recovery
- **launchd fix command** — `fix` reinstalls missing service files for running processes
- **TCC path protection** — `--sudo` processes are blocked from using TCC-protected directories (Desktop, Documents, Downloads) that would fail when run as LaunchDaemons (macOS only)
- **Sudo support** — `--sudo` flag to run processes with elevated privileges
- **Session isolation** — processes spawned in new sessions survive terminal closure
- **Coloured output** — TTY-aware ANSI colours for status display and log prefixes
- **Zero dependencies** — stdlib only, no external packages required
