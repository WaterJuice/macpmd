# macpmd

A macOS process manager — a PM2 equivalent using launchd for persistence and crash recovery.

macpmd makes it easy to manage long-running processes on macOS. Start, stop, restart, and monitor processes from the command line. Processes are automatically registered with launchd so they survive reboots and recover from crashes.

## Features

- **Process management** — add, start, stop, restart, and delete processes
- **Batch operations** — operate on multiple processes at once, or use `--all`
- **Process listing** — view all processes with status, PID, uptime, restart count, and launchd state
- **Log management** — stdout/stderr redirected to `~/.local/share/macpmd/logs/` with automatic rotation
- **Log tailing** — view recent output, follow in real-time, or show all process logs with coloured prefixes
- **Exit code logging** — process exit codes and signals are recorded in the log
- **launchd integration** — plists auto-installed in `~/Library/LaunchAgents/` for boot persistence and crash recovery
- **Sudo support** — start processes with `--sudo` for elevated privileges
- **Zero dependencies** — stdlib only, no external packages required
- **Coloured output** — TTY-aware ANSI colours for status display

## Requirements

- Python 3.12+
- macOS (uses launchd and launchctl)

## Installation

```bash
pip install macpmd
```

Or run directly with uv:

```bash
uvx macpmd
```

## Quick Start

```bash
# Add a process (name auto-derived as "server")
macpmd add "node server.js"

# Add with an explicit name
macpmd add "python3 worker.py" --name my-worker

# Add with sudo
macpmd add "python3 server.py" --name my-app --sudo

# List all processes
macpmd list

# View logs
macpmd logs my-app
macpmd logs my-app --follow
macpmd logs --all
macpmd logs --all --follow

# Start a stopped process
macpmd start my-app

# Start all stopped processes
macpmd start --all

# Restart a process
macpmd restart my-app

# Stop multiple processes
macpmd stop my-app worker

# Stop all processes
macpmd stop --all

# Remove a process entirely
macpmd delete my-app
```

## How It Works

macpmd spawns processes in new sessions (`start_new_session`) so they survive the parent terminal closing. Process state is tracked in `~/.local/share/macpmd/state.json` and logs are written to `~/.local/share/macpmd/logs/<name>.log`.

When you add a process, a launchd plist is automatically installed in `~/Library/LaunchAgents/` with:

- **`KeepAlive: true`** — launchd restarts the process if it crashes
- **`RunAtLoad: true`** — the process starts automatically at login

This gives you PM2-style process management backed by macOS's native process supervisor.

## Development

```bash
# Set up development environment
make dev

# Run linting and type checking
make check

# Auto-format code
make format

# Build wheel and docs
make build
```

## Licence

Released under the [Unlicense](https://unlicense.org/) — public domain.
