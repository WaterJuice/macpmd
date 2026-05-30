# macpmd 1.0.2 — 30 May 2026

Minor change for building environment, no code changes.

# macpmd 1.0.1 — 21 May 2026

## Fixes

- **Single-launch start** — `add`, `start`, and `restart` no longer launch the process twice. Previously the process was spawned directly *and* by the service manager (launchd `RunAtLoad` / systemd `enable --now`), leaving two concurrent copies — or a crash-looping duplicate for single-instance services. The service manager is now the sole launcher, so the first run after `add` uses exactly the same context (session, environment, working directory) as a relaunch after reboot or crash. The tracked PID is read back from the service manager.
- **`fix`** now relaunches a running-but-unmanaged process under the service manager (the manager cannot adopt an existing process) instead of installing a service alongside the existing copy.

## Packaging

- Marked Production/Stable.
- Added documentation link: https://docs.waterjuice.org/macpmd/latest/

# macpmd 1.0.0 — 9 Apr 2026

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
- **Cross-platform service backend** — platform-specific service managers selected automatically (launchd on macOS, systemd on Linux)
- **launchd integration (macOS)** — plists auto-installed on `add` in `~/Library/LaunchAgents/` (standard) or `/Library/LaunchDaemons/` (sudo) for boot persistence and crash recovery
- **systemd integration (Linux)** — units auto-installed on `add` in `~/.config/systemd/user/` (standard) or `/etc/systemd/system/` (sudo) with `Restart=always` for crash recovery
- **Fix command** — `fix` reinstalls missing service files for running processes
- **TCC path protection (macOS)** — `--sudo` processes are blocked from using TCC-protected directories (Desktop, Documents, Downloads) that would fail when run as LaunchDaemons
- **Sudo support** — `--sudo` flag to run processes with elevated privileges
- **Session isolation** — processes spawned in new sessions survive terminal closure
- **Coloured output** — TTY-aware ANSI colours for status display and log prefixes
- **Zero dependencies** — stdlib only, no external packages required
