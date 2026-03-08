# ----------------------------------------------------------------------------------------
#   logs.py
#   -------
#
#   Log file management for managed processes. Handles log file paths and
#   tailing log output. Logs are stored in ~/.local/share/macpmd/logs/
#   with rotation via RotatingFileHandler-style rotation.
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

import io
import os
import time
from pathlib import Path
from .colour import colourise
from .state import LOGS_DIR
from .state import ensure_dirs

# ----------------------------------------------------------------------------------------
#   Constants
# ----------------------------------------------------------------------------------------

MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_LOG_FILES = 3

# ----------------------------------------------------------------------------------------
#   Functions
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def get_log_path(name: str) -> Path:
    """Return the log file path for a process."""
    ensure_dirs()
    return LOGS_DIR / f"{name}.log"


# ----------------------------------------------------------------------------------------
def rotate_log(name: str) -> None:
    """Rotate log files if the current one exceeds MAX_LOG_SIZE."""
    log_path = get_log_path(name)
    if not log_path.exists():
        return

    try:
        size = log_path.stat().st_size
    except OSError:
        return

    if size < MAX_LOG_SIZE:
        return

    # Rotate: name.log.2 -> name.log.3, name.log.1 -> name.log.2, etc.
    for i in range(MAX_LOG_FILES - 1, 0, -1):
        src = LOGS_DIR / f"{name}.log.{i}"
        dst = LOGS_DIR / f"{name}.log.{i + 1}"
        if src.exists():
            src.rename(dst)

    # Current log becomes .1
    log_path.rename(LOGS_DIR / f"{name}.log.1")


# ----------------------------------------------------------------------------------------
def _read_all_log_files(name: str) -> list[str]:
    """Read all log files for a process (rotated + current), oldest first."""
    all_lines: list[str] = []

    # Read rotated files in reverse order (oldest first)
    for i in range(MAX_LOG_FILES, 0, -1):
        rotated = LOGS_DIR / f"{name}.log.{i}"
        if rotated.exists():
            try:
                content = rotated.read_text(encoding="utf-8", errors="replace")
                all_lines.extend(content.splitlines())
            except OSError:
                pass

    # Read current log file
    log_path = get_log_path(name)
    if log_path.exists():
        try:
            content = log_path.read_text(encoding="utf-8", errors="replace")
            all_lines.extend(content.splitlines())
        except OSError:
            pass

    return all_lines


# ----------------------------------------------------------------------------------------
def tail_log(name: str, lines: int = 50) -> str:
    """Return the last N lines from all log files (including rotated)."""
    all_lines = _read_all_log_files(name)
    if not all_lines:
        return f"No log file found for '{name}'."

    if lines > 0:
        all_lines = all_lines[-lines:]
    return "\n".join(all_lines)


# ----------------------------------------------------------------------------------------
def follow_log(name: str) -> None:
    """Follow a log file in real-time (like tail -f). Blocks until interrupted."""
    log_path = get_log_path(name)
    if not log_path.exists():
        # Create the file so we can follow it
        log_path.touch()

    with open(log_path, encoding="utf-8", errors="replace") as f:
        # Seek to end
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                print(line, end="")
            else:
                try:
                    time.sleep(0.1)
                except KeyboardInterrupt:
                    break


# ----------------------------------------------------------------------------------------
def follow_logs_all(names: list[str]) -> None:
    """Follow log files for multiple processes concurrently. Blocks until interrupted."""
    # Assign a colour index to each name
    colour_map: dict[str, int] = {n: i for i, n in enumerate(names)}

    # Ensure all log files exist
    files: dict[str, Path] = {}
    for name in names:
        log_path = get_log_path(name)
        if not log_path.exists():
            log_path.touch()
        files[name] = log_path

    # Open all files and seek to end
    handles: dict[str, io.TextIOWrapper] = {}
    try:
        for name, path in files.items():
            fh = open(path, encoding="utf-8", errors="replace")  # noqa: SIM115
            fh.seek(0, os.SEEK_END)
            handles[name] = fh

        while True:
            had_output = False
            for name, fh in handles.items():
                line = fh.readline()
                if line:
                    had_output = True
                    prefix = colourise(name, colour_map[name])
                    print(f"{prefix} | {line}", end="")
            if not had_output:
                try:
                    time.sleep(0.1)
                except KeyboardInterrupt:
                    break
    finally:
        for fh in handles.values():
            fh.close()


# ----------------------------------------------------------------------------------------
def prefix_log_lines(name: str, text: str, colour_index: int = 0) -> str:
    """Prefix each line of log text with the coloured process name."""
    if not text:
        return text
    prefix = colourise(name, colour_index)
    lines = text.splitlines()
    return "\n".join(f"{prefix} | {line}" for line in lines)


# ----------------------------------------------------------------------------------------
def delete_logs(name: str) -> None:
    """Delete all log files for a process (including rotated ones)."""
    log_path = get_log_path(name)
    if log_path.exists():
        log_path.unlink()

    for i in range(1, MAX_LOG_FILES + 1):
        rotated = LOGS_DIR / f"{name}.log.{i}"
        if rotated.exists():
            rotated.unlink()
