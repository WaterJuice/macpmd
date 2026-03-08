# ----------------------------------------------------------------------------------------
#   state.py
#   --------
#
#   Manages process state persistence in ~/.macpmd/state.json. Handles reading,
#   writing, and updating process records.
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

import json
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------------------------
#   Constants
# ----------------------------------------------------------------------------------------

MACPMD_DIR = Path.home() / ".local" / "share" / "macpmd"
STATE_FILE = MACPMD_DIR / "state.json"
LOGS_DIR = MACPMD_DIR / "logs"

# ----------------------------------------------------------------------------------------
#   Types
# ----------------------------------------------------------------------------------------


@dataclass
class ProcessEntry:
    """
    Represents a managed process.

    Attributes:
        name: Unique name for the process.
        command: The shell command to run.
        cwd: Working directory when the process was started.
        pid: PID of the running process (0 if not running).
        status: Current status (running, stopped, errored).
        started_at: ISO timestamp of when the process was last started.
        restarts: Number of times the process has been restarted.
        sudo: Whether to run the command with sudo.
        env: Environment variables captured at start time.
    """

    name: str
    command: str
    cwd: str
    pid: int = 0
    status: str = "stopped"
    started_at: str = ""
    restarts: int = 0
    sudo: bool = False
    env: dict[str, str] = field(default_factory=lambda: dict[str, str]())


# ----------------------------------------------------------------------------------------
#   Functions
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def ensure_dirs() -> None:
    """Create the macpmd directories if they do not exist."""
    MACPMD_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------------------------
def load_state() -> dict[str, ProcessEntry]:
    """Load process state from disk. Returns empty dict if file does not exist."""
    if not STATE_FILE.exists():
        return {}

    try:
        raw: object = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(raw, dict):
        return {}

    processes: dict[str, ProcessEntry] = {}
    procs_raw: object = raw.get("processes", {})  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    if not isinstance(procs_raw, dict):
        return {}

    items: list[tuple[object, object]] = list(procs_raw.items())  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
    for name_key, entry_val in items:
        if not isinstance(name_key, str) or not isinstance(entry_val, dict):
            continue
        e: dict[str, object] = dict(entry_val)  # pyright: ignore[reportUnknownArgumentType]
        command = e.get("command", "")
        cwd = e.get("cwd", "")
        pid = e.get("pid", 0)
        status = e.get("status", "stopped")
        started_at = e.get("started_at", "")
        restarts = e.get("restarts", 0)
        sudo = e.get("sudo", False)
        env_raw = e.get("env", {})
        processes[name_key] = ProcessEntry(
            name=name_key,
            command=str(command),
            cwd=str(cwd),
            pid=int(pid) if isinstance(pid, int) else 0,
            status=str(status),
            started_at=str(started_at),
            restarts=int(restarts) if isinstance(restarts, int) else 0,
            sudo=bool(sudo),
            env=(dict(env_raw) if isinstance(env_raw, dict) else {}),  # pyright: ignore[reportUnknownArgumentType]
        )

    return processes


# ----------------------------------------------------------------------------------------
def save_state(processes: dict[str, ProcessEntry]) -> None:
    """Write process state to disk."""
    ensure_dirs()
    data: dict[str, Any] = {
        "processes": {name: asdict(entry) for name, entry in processes.items()},
    }
    STATE_FILE.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ----------------------------------------------------------------------------------------
def get_process(name: str) -> ProcessEntry | None:
    """Get a single process entry by name, or None if not found."""
    processes = load_state()
    return processes.get(name)


# ----------------------------------------------------------------------------------------
def update_process(entry: ProcessEntry) -> None:
    """Update (or add) a single process entry in state."""
    processes = load_state()
    processes[entry.name] = entry
    save_state(processes)


# ----------------------------------------------------------------------------------------
def remove_process(name: str) -> bool:
    """Remove a process entry from state. Returns True if it existed."""
    processes = load_state()
    if name not in processes:
        return False
    del processes[name]
    save_state(processes)
    return True
