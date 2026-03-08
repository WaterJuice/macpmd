# macpmd

A macOS process manager — a PM2 equivalent using launchd for persistence and crash recovery.

## Why?

Managing long-running processes on macOS is awkward. You can run things in the background with `&` or `nohup`, but they don't survive reboots, there's no easy way to check their status, and crash recovery requires manual scripting. PM2 solves this on Linux/Node.js, but macOS has its own process supervision system: launchd.

macpmd bridges the gap — a simple CLI for managing processes that integrates with launchd for boot persistence and automatic crash recovery.

## Features

- **Process management** — start, stop, restart, and delete processes
- **Batch operations** — operate on multiple processes at once, or use `--all`
- **Process listing** — view all processes with status, PID, uptime, restart count, and launchd state
- **Log management** — stdout/stderr redirected to `~/.local/share/macpmd/logs/` with automatic rotation
- **Log tailing** — view recent output, follow in real-time, or show all process logs with coloured prefixes
- **Exit code logging** — process exit codes and signals are recorded in the log
- **launchd integration** — plists auto-installed on `start` for boot persistence and crash recovery
- **Sudo support** — start processes with `--sudo` for elevated privileges
- **Session isolation** — processes survive terminal closure
- **Zero dependencies** — stdlib only

## Requirements

- Python 3.10+
- macOS (uses launchd and launchctl)

## Quick Start

### Install

```bash
pip install macpmd
```

Or run directly with uv:

```bash
uvx macpmd
```

### Start a process

```bash
macpmd start "node server.js" --name my-app
```

This automatically installs a launchd plist so the process survives reboots and recovers from crashes.

### List processes

```bash
macpmd list
```

### View logs

```bash
macpmd logs my-app
macpmd logs --all --follow
```

See the [Usage](usage.md) page for full details on all commands.

## How It Works

macpmd spawns processes in new sessions so they survive the parent terminal closing. Process state is tracked in `~/.local/share/macpmd/state.json` and logs are written to `~/.local/share/macpmd/logs/<name>.log`.

When you start a process, a launchd plist is automatically installed in `~/Library/LaunchAgents/` with:

- **`KeepAlive: true`** — launchd restarts the process if it crashes
- **`RunAtLoad: true`** — the process starts automatically at login

This gives you PM2-style process management backed by macOS's native process supervisor.
