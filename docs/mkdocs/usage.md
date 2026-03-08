# Usage

macpmd provides a command-line interface for managing long-running processes on macOS.

## `start` — Start a process

```bash
macpmd start "<command>" --name <name>
macpmd start "<command>" --name <name> --sudo
```

Starts a new process and registers it with macpmd. The command is executed via the shell, so pipes, environment variables, and other shell features work. A launchd plist is automatically installed so the process survives reboots and recovers from crashes.

```bash
# Start a Node.js server
macpmd start "node server.js" --name my-api

# Start a Python script
macpmd start "python3 worker.py" --name worker

# Start with sudo
macpmd start "python3 server.py" --name privileged-app --sudo

# Start with shell features
macpmd start "cd /opt/app && ./run.sh 2>&1 | tee extra.log" --name app
```

The process is spawned in a new session, so it continues running after the terminal closes. The working directory and environment are captured at start time.

| Option          | Description                              |
|-----------------|------------------------------------------|
| `--name`, `-n`  | Name for the process (required)          |
| `--sudo`, `-s`  | Run the process with sudo                |

## `stop` — Stop processes

```bash
macpmd stop <name> [<name> ...]
macpmd stop --all
```

Sends SIGTERM to the process group. If the process does not exit within 3 seconds, SIGKILL is sent. The launchd plist is uninstalled first so launchd does not restart the process.

```bash
# Stop a single process
macpmd stop my-api

# Stop multiple processes
macpmd stop my-api worker

# Stop all processes
macpmd stop --all
```

## `restart` — Restart processes

```bash
macpmd restart <name> [<name> ...]
macpmd restart --all
```

Stops the process (if running) and starts it again. The restart counter is incremented. The launchd plist is reinstalled with the updated state.

```bash
# Restart a single process
macpmd restart my-api

# Restart multiple processes
macpmd restart my-api worker

# Restart all processes
macpmd restart --all
```

## `delete` — Remove processes

```bash
macpmd delete <name> [<name> ...]
macpmd delete --all
```

Stops the process (if running), uninstalls its launchd plist, deletes its log files, and removes it from macpmd's state.

```bash
# Delete a single process
macpmd delete my-api

# Delete multiple processes
macpmd delete my-api worker

# Delete all processes
macpmd delete --all
```

## `list` — Show all processes

```bash
macpmd list
```

Displays a table of all registered processes with:

| Column   | Description                                          |
|----------|------------------------------------------------------|
| Name     | Process name                                         |
| Status   | `running`, `stopped`, or `errored`                   |
| PID      | Process ID (if running)                              |
| Uptime   | Time since the process was last started               |
| Restarts | Number of times the process has been restarted        |
| launchd  | Whether a launchd plist is installed                  |

Process statuses are refreshed automatically — if a process has died since the last check, its status is updated to `errored`.

## `logs` — View process logs

```bash
macpmd logs <name> [<name> ...]
macpmd logs --all
macpmd logs <name> --follow
macpmd logs --all --follow
```

All process output (stdout and stderr) is captured in `~/.local/share/macpmd/logs/<name>.log`. Logs span across rotated files, so you can see the full history.

| Option          | Description                                        |
|-----------------|----------------------------------------------------|
| `--lines`, `-l` | Number of lines to show (default: 50, 0 for all)  |
| `--follow`, `-f`| Follow log output in real-time                     |
| `--all`, `-a`   | Show logs for all processes                        |

When viewing logs for multiple processes (either by naming several or using `--all`), each line is prefixed with the coloured process name, docker-compose style:

```
my-api | [12:34:56] Server started on port 3000
worker | [12:34:57] Processing job 42
```

When using `--follow`, the last N lines are shown first (controlled by `--lines`), then new output is displayed in real-time. Press Ctrl+C to stop following.

### Lifecycle Events

macpmd logs process lifecycle events with a `[macpmd]` prefix:

```
[macpmd] Process started at 2026-03-08 12:34:56 UTC (PID 1234)
... process output ...
[macpmd] Process exited at 2026-03-08 12:35:56 UTC with code 0
[macpmd] Process restarting at 2026-03-08 12:35:57 UTC (restart #1)
[macpmd] Process started at 2026-03-08 12:35:57 UTC (PID 1235)
```

### Log Rotation

Log files are rotated automatically when they exceed 10 MB. Up to 3 rotated files are kept:

```
~/.local/share/macpmd/logs/my-app.log      # Current log
~/.local/share/macpmd/logs/my-app.log.1    # Previous
~/.local/share/macpmd/logs/my-app.log.2    # Older
~/.local/share/macpmd/logs/my-app.log.3    # Oldest
```

The `logs` command reads across all rotated files, so `--lines 50` gives you the last 50 lines from the full history. Use `--lines 0` to show all available log history.

## Global Options

| Option       | Description                         |
|--------------|-------------------------------------|
| `--version`  | Show version and exit               |
| `--license`  | Show licence information and exit   |
| `--help`     | Show help and exit                  |

## File Locations

| Path                                | Purpose                          |
|-------------------------------------|----------------------------------|
| `~/.local/share/macpmd/state.json`             | Process state and configuration  |
| `~/.local/share/macpmd/logs/<name>.log`        | Process stdout/stderr            |
| `~/Library/LaunchAgents/com.macpmd.<name>.plist` | launchd plist    |
