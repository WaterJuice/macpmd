# ----------------------------------------------------------------------------------------
#   process.py
#   ----------
#
#   Process spawning and management. Uses subprocess.Popen with os.setsid()
#   for process group isolation. Handles starting, stopping, and checking
#   process status.
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

import os
import re
import signal
import subprocess
import time
from datetime import UTC
from datetime import datetime
from .logs import get_log_path
from .logs import rotate_log
from .state import ProcessEntry
from .state import load_state
from .state import save_state
from .state import update_process

# ----------------------------------------------------------------------------------------
#   Functions
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
_PID_RE = re.compile(r"\[macpmd\] Process started at .+ \(PID (\d+)\)")


# ----------------------------------------------------------------------------------------
def _get_pid_from_log(name: str) -> int:
    """Parse the most recent PID from the log file's [macpmd] start lines.

    This is used as a fallback when launchctl cannot be queried (e.g. sudo
    processes without cached credentials).
    """
    log_path = get_log_path(name)
    if not log_path.exists():
        return 0

    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    last_pid = 0
    for match in _PID_RE.finditer(content):
        last_pid = int(match.group(1))

    return last_pid


# ----------------------------------------------------------------------------------------
def _discover_pid(name: str, sudo: bool) -> int:
    """Try to find the current PID for a process via launchctl or log fallback."""
    from .launchd import get_launchd_pid

    pid = get_launchd_pid(name, sudo=sudo)
    if pid > 0:
        return pid

    # Fallback: parse PID from log file (works even when sudo -n fails)
    return _get_pid_from_log(name)


# ----------------------------------------------------------------------------------------
def is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we cannot signal it
        return True


# ----------------------------------------------------------------------------------------
def refresh_status(entry: ProcessEntry) -> ProcessEntry:
    """Update a process entry's status based on whether its PID is alive.

    If the stored PID is dead but a launchd plist is installed, queries launchd
    for the real PID (launchd may have restarted the process).
    """
    from .launchd import is_plist_installed

    if entry.status == "running" and entry.pid > 0:
        if not is_process_alive(entry.pid):
            # Check if launchd restarted the process with a new PID
            if is_plist_installed(entry.name):
                new_pid = _discover_pid(entry.name, entry.sudo)
                if new_pid > 0 and is_process_alive(new_pid):
                    entry.pid = new_pid
                    entry.restarts += 1
                    return entry
            entry.status = "errored"
            entry.pid = 0
    elif entry.status in ("errored", "stopped") and is_plist_installed(entry.name):
        # Process was marked dead but launchd may have restarted it
        new_pid = _discover_pid(entry.name, entry.sudo)
        if new_pid > 0 and is_process_alive(new_pid):
            entry.pid = new_pid
            entry.status = "running"
            entry.restarts += 1
    return entry


# ----------------------------------------------------------------------------------------
def refresh_all_statuses() -> dict[str, ProcessEntry]:
    """Load state and refresh the status of all processes."""
    processes = load_state()
    for entry in processes.values():
        refresh_status(entry)
    save_state(processes)
    return processes


# ----------------------------------------------------------------------------------------
def _log_event(log_path_str: str, event: str) -> None:
    """Append a [macpmd] event line to the log file."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        with open(log_path_str, "a", encoding="utf-8") as f:
            f.write(f"[macpmd] {event} at {timestamp}\n")
    except OSError:
        pass


# ----------------------------------------------------------------------------------------
def wrap_command(command: str) -> str:
    """Wrap a command so it logs start and exit events to stdout.

    Since stdout is redirected to the log file, printf output goes there.
    This works both when macpmd spawns the process and when launchd restarts it.
    """
    # Use a subshell so $? captures the command's exit code, not printf's
    ts = "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    return (
        f'printf \'[macpmd] Process started at %s (PID %s)\\n\' "{ts}" "$$"; '
        f"( {command} ); "
        f"_macpmd_rc=$?; "
        f'printf \'[macpmd] Process exited at %s with code %d\\n\' "{ts}" "$_macpmd_rc"; '
        f'exit "$_macpmd_rc"'
    )


# ----------------------------------------------------------------------------------------
def start_process(entry: ProcessEntry) -> tuple[bool, str]:
    """
    Start a process. Returns (success, message).

    The process is spawned in a new session (os.setsid) so it survives
    the parent terminal closing. stdout and stderr are redirected to the
    log file. The command is wrapped to log start and exit events.
    """
    # If already running, do not start again
    if entry.status == "running" and is_process_alive(entry.pid):
        return False, f"Process '{entry.name}' is already running (PID {entry.pid})."

    # Rotate log if needed before starting
    rotate_log(entry.name)

    log_path = get_log_path(entry.name)
    cwd = entry.cwd if entry.cwd else None

    try:
        log_file = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    except OSError as e:
        return False, f"Failed to open log file: {e}"

    shell_command = f"sudo {entry.command}" if entry.sudo else entry.command
    wrapped_command = wrap_command(shell_command)

    try:
        proc = subprocess.Popen(
            wrapped_command,
            shell=True,  # noqa: S602
            cwd=cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=entry.env if entry.env else None,
        )
    except OSError as e:
        log_file.close()
        return False, f"Failed to start process: {e}"

    entry.pid = proc.pid
    entry.status = "running"
    entry.started_at = datetime.now(UTC).isoformat()
    update_process(entry)

    # Close our handle to the log file — the child process has its own
    log_file.close()

    return True, f"Process '{entry.name}' started (PID {proc.pid})."


# ----------------------------------------------------------------------------------------
def _sudo_kill(pid: int, sig: signal.Signals) -> None:
    """Send a signal to a process using sudo kill."""
    try:
        subprocess.run(
            ["sudo", "-n", "kill", f"-{sig.value}", str(pid)],  # noqa: S603, S607
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


# ----------------------------------------------------------------------------------------
def stop_process(entry: ProcessEntry) -> tuple[bool, str]:
    """
    Stop a running process. Sends SIGTERM, then SIGKILL after a timeout.
    Returns (success, message).
    """
    if entry.pid <= 0 or not is_process_alive(entry.pid):
        entry.status = "stopped"
        entry.pid = 0
        update_process(entry)
        return True, f"Process '{entry.name}' is not running."

    pid = entry.pid

    if entry.sudo:
        _sudo_kill(pid, signal.SIGTERM)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass

    # Wait briefly for the process to exit
    for _ in range(30):  # 3 seconds
        if not is_process_alive(pid):
            break
        time.sleep(0.1)

    # If still alive, send SIGKILL
    if is_process_alive(pid):
        if entry.sudo:
            _sudo_kill(pid, signal.SIGKILL)
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

    entry.status = "stopped"
    entry.pid = 0
    update_process(entry)

    return True, f"Process '{entry.name}' stopped."


# ----------------------------------------------------------------------------------------
def restart_process(entry: ProcessEntry) -> tuple[bool, str]:
    """Stop and restart a process. Returns (success, message)."""
    if entry.status == "running" and is_process_alive(entry.pid):
        ok, msg = stop_process(entry)
        if not ok:
            return False, msg

    entry.restarts += 1
    _log_event(
        str(get_log_path(entry.name)), f"Process restarting (restart #{entry.restarts})"
    )
    ok, msg = start_process(entry)
    return ok, msg
