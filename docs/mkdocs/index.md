# macpmd

A macOS process manager — a PM2 equivalent using launchd for persistence and crash recovery.

## Why?

Managing long-running processes on macOS is awkward. You can run things in the background with `&` or `nohup`, but they don't survive reboots, there's no easy way to check their status, and crash recovery requires manual scripting. PM2 solves this on Linux/Node.js, but macOS has its own process supervision system: launchd.

macpmd bridges the gap — a simple CLI for managing processes that integrates with launchd for boot persistence and automatic crash recovery.

## Features

- **Process management** — add, start, stop, restart, and delete processes
- **Batch operations** — operate on multiple processes at once, or use `--all`
- **Process listing** — view all processes with status, PID, uptime, restart count, sudo, and launchd state
- **Process info** — detailed view of any process including full command, with JSON output support
- **Log management** — stdout/stderr redirected to `~/.local/share/macpmd/logs/` with automatic rotation
- **Log tailing** — view recent output, follow in real-time, or show all process logs with coloured prefixes
- **Exit code logging** — process exit codes and signals are recorded in the log
- **Immediate failure detection** — commands that fail on `add` are reported immediately and not persisted
- **launchd integration** — plists auto-installed on `add` for boot persistence and crash recovery
- **Self-healing** — `fix` command reinstalls missing launchd plists
- **Sudo support** — start processes with `--sudo` for elevated privileges (uses LaunchDaemons)
- **TCC path protection** — prevents `--sudo` processes from using macOS-protected directories
- **Session isolation** — processes survive terminal closure
- **Zero dependencies** — stdlib only

## Requirements

- Python 3.12+
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

### Add a process

```bash
macpmd add "node server.js"
```

The name is auto-derived from the command (`server` in this case), or you can specify one with `--name`. A launchd plist is automatically installed so the process survives reboots and recovers from crashes.

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

When you add a process, a launchd plist is automatically installed in `~/Library/LaunchAgents/` (or `/Library/LaunchDaemons/` for `--sudo` processes) with:

- **`KeepAlive: true`** — launchd restarts the process if it crashes
- **`RunAtLoad: true`** — the process starts automatically at login

This gives you PM2-style process management backed by macOS's native process supervisor.
