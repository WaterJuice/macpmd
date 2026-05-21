# ----------------------------------------------------------------------------------------
#   process.py
#   ----------
#
#   Process spawning and management. The service manager (launchd on macOS,
#   systemd on Linux) is the sole launcher: starting a process installs its
#   service, which launches it, and the PID is read back from the manager.
#   Handles starting, stopping, restarting, and checking process status.
#
#   (c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
#
#   Version History
#   ---------------
#   Mar 2026 - Created
#   May 2026 - Launch via the service manager only (no direct Popen spawn)
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
    """Try to find the current PID for a process via the service backend or log fallback."""
    from .backend import get_backend

    pid = get_backend().get_service_pid(name, sudo=sudo)
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

    If the stored PID is dead but a service file is installed, queries the
    service backend for the real PID (it may have restarted the process).
    """
    from .backend import get_backend

    backend = get_backend()

    if entry.status == "running" and entry.pid > 0:
        if not is_process_alive(entry.pid):
            # Check if the service manager restarted the process with a new PID
            if backend.is_service_installed(entry.name):
                new_pid = _discover_pid(entry.name, entry.sudo)
                if new_pid > 0 and is_process_alive(new_pid):
                    entry.pid = new_pid
                    entry.restarts += 1
                    return entry
            entry.status = "errored"
            entry.pid = 0
    elif entry.status in ("errored", "stopped") and backend.is_service_installed(
        entry.name
    ):
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
def _read_last_log_lines(name: str, max_lines: int = 5) -> str:
    """Read the last few lines from a process log file for error context."""
    log_path = get_log_path(name)
    if not log_path.exists():
        return ""
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            return ""
        lines = content.splitlines()[-max_lines:]
        return "\n".join(lines)
    except OSError:
        return ""


# ----------------------------------------------------------------------------------------
def wrap_command(command: str) -> str:
    """Wrap a command so it logs start and exit events to stdout.

    Since stdout is redirected to the log file, printf output goes there.
    This works both when macpmd spawns the process and when launchd restarts it.
    """
    # Use a subshell so $? captures the command's exit code, not printf's
    ts = "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    return (
        f'printf \'[macpmd] Process started at %s (PID %s)\\n\' "{ts}" "$$"; ('
        f" {command} ); _macpmd_rc=$?; printf '[macpmd] Process exited at %s with code"
        f' %d\\n\' "{ts}" "$_macpmd_rc"; exit "$_macpmd_rc"'
    )


# ----------------------------------------------------------------------------------------
_START_SETTLE_SECONDS = 1.5


# ----------------------------------------------------------------------------------------
def _await_service_pid(entry: ProcessEntry) -> int:
    """Wait for the service manager to report a stable, live PID after start.

    Sleeps a short settle period so that an immediate failure (a missing
    executable, a permission error, an instantly-exiting command) has time to
    manifest: a crash-looping service is throttled by launchd/systemd, so its
    PID reads as 0 here. Returns the live PID, or 0 if the process never came up.
    """
    from .backend import get_backend

    backend = get_backend()
    time.sleep(_START_SETTLE_SECONDS)
    for _ in range(3):
        pid = backend.get_service_pid(entry.name, sudo=entry.sudo)
        if pid > 0 and is_process_alive(pid):
            return pid
        time.sleep(0.2)
    return 0


# ----------------------------------------------------------------------------------------
def start_process(entry: ProcessEntry) -> tuple[bool, str]:
    """
    Start a process by installing its service and letting the service manager
    launch it. Returns (success, message).

    The service manager (launchd on macOS, systemd on Linux) is the sole
    launcher: it runs the command at install time, on boot, and after a crash.
    Routing the first launch through it too means an `add` runs the process in
    exactly the same context (session, environment, working directory) as a
    relaunch after reboot — there is never a second, unmanaged copy.
    """
    from .backend import get_backend

    backend = get_backend()

    # If already running, do not start again
    if entry.status == "running" and is_process_alive(entry.pid):
        return False, f"Process '{entry.name}' is already running (PID {entry.pid})."

    # Rotate log if needed so the start banner lands in a fresh file
    rotate_log(entry.name)

    # Install the service. This also launches the process (RunAtLoad on launchd,
    # `enable --now` on systemd).
    ok, msg = backend.install_service(entry)
    if not ok:
        entry.status = "errored"
        entry.pid = 0
        update_process(entry)
        return False, msg

    # Confirm the process actually came up. If it failed immediately, tear the
    # service down so it does not crash-loop, and surface recent log output.
    pid = _await_service_pid(entry)
    if pid <= 0:
        backend.uninstall_service(entry.name, sudo=entry.sudo)
        entry.status = "errored"
        entry.pid = 0
        update_process(entry)
        hint = _read_last_log_lines(entry.name, max_lines=5)
        msg = f"Process '{entry.name}' failed to start (exited immediately)."
        if hint:
            msg += f"\n{hint}"
        return False, msg

    entry.pid = pid
    entry.status = "running"
    entry.started_at = datetime.now(UTC).isoformat()
    update_process(entry)

    return True, f"Process '{entry.name}' started (PID {pid})."


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
    Stop a process and remove its service so the service manager does not
    relaunch it. Sends SIGTERM to the tracked process, then SIGKILL after a
    timeout. Returns (success, message).
    """
    from .backend import get_backend

    backend = get_backend()

    # Uninstall the service first so launchd/systemd does not immediately
    # restart the process the moment we kill it. (Unloading the service also
    # signals the managed process, so the tracked PID may already be gone.)
    if backend.is_service_installed(entry.name):
        backend.uninstall_service(entry.name, sudo=entry.sudo)

    pid = entry.pid
    if pid > 0 and is_process_alive(pid):
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
    """Stop and restart a process. Returns (success, message).

    stop_process removes the service (and kills any running copy); start_process
    reinstalls it and relaunches via the service manager.
    """
    ok, msg = stop_process(entry)
    if not ok:
        return False, msg

    entry.restarts += 1
    _log_event(
        str(get_log_path(entry.name)), f"Process restarting (restart #{entry.restarts})"
    )
    ok, msg = start_process(entry)
    return ok, msg
