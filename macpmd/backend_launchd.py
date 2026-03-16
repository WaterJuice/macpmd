# ----------------------------------------------------------------------------------------
#   backend_launchd.py
#   ------------------
#
#   launchd service backend for macOS. Generates and manages plist files in
#   ~/Library/LaunchAgents/ (user agents) and /Library/LaunchDaemons/ (system
#   daemons) for boot persistence and crash recovery via KeepAlive.
#
#   (c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
#
#   Version History
#   ---------------
#   Mar 2026 - Created (refactored from launchd.py)
# ----------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------------------------

import plistlib
import subprocess
from pathlib import Path
from .backend import ServiceBackend
from .logs import get_log_path
from .process import wrap_command
from .state import ProcessEntry
from .state import load_state

# ----------------------------------------------------------------------------------------
#   Constants
# ----------------------------------------------------------------------------------------

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCH_DAEMONS_DIR = Path("/Library/LaunchDaemons")
PLIST_PREFIX = "com.macpmd"

# ----------------------------------------------------------------------------------------
#   Backend
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
class LaunchdBackend(ServiceBackend):
    """macOS launchd service backend."""

    # ------------------------------------------------------------------------------------
    def service_label(self) -> str:
        """Return the display label for this backend."""
        return "launchd"

    # ------------------------------------------------------------------------------------
    def install_service(self, entry: ProcessEntry) -> tuple[bool, str]:
        """Generate and install a launchd plist for a process."""
        use_sudo = entry.sudo
        plist_path = _plist_path(entry.name, sudo=use_sudo)
        sudo_prefix: list[str] = ["sudo"] if use_sudo else []

        if use_sudo:
            LAUNCH_DAEMONS_DIR.mkdir(parents=True, exist_ok=True)
        else:
            LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

        # Unload existing plist if present
        if plist_path.exists():
            subprocess.run(
                [*sudo_prefix, "launchctl", "unload", str(plist_path)],  # noqa: S603, S607
                capture_output=True,
                timeout=10,
            )

        try:
            plist_data = _generate_plist(entry)
            if use_sudo:
                # Write via sudo tee since we cannot write to /Library/LaunchDaemons directly
                proc = subprocess.run(
                    ["sudo", "tee", str(plist_path)],  # noqa: S603, S607
                    input=plist_data,
                    capture_output=True,
                    timeout=10,
                )
                if proc.returncode != 0:
                    return (
                        False,
                        f"Failed to write plist: {proc.stderr.decode().strip()}",
                    )
            else:
                plist_path.write_bytes(plist_data)
        except OSError as e:
            return False, f"Failed to write plist: {e}"

        # Load the plist
        result = subprocess.run(
            [*sudo_prefix, "launchctl", "load", str(plist_path)],  # noqa: S603, S607
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            return False, f"Failed to load plist: {stderr}"

        return True, f"Installed launchd plist for '{entry.name}'."

    # ------------------------------------------------------------------------------------
    def uninstall_service(self, name: str, sudo: bool = False) -> tuple[bool, str]:
        """Unload and remove a launchd plist for a process."""
        plist_path = _plist_path(name, sudo=sudo)
        sudo_prefix: list[str] = ["sudo"] if sudo else []

        if not plist_path.exists():
            # Check the other location in case sudo flag changed
            alt_path = _plist_path(name, sudo=not sudo)
            if alt_path.exists():
                plist_path = alt_path
                if not sudo:
                    sudo_prefix = ["sudo"]
            else:
                return True, f"No launchd plist found for '{name}'."

        # Unload
        result = subprocess.run(
            [*sudo_prefix, "launchctl", "unload", str(plist_path)],  # noqa: S603, S607
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Remove the file regardless of unload result
        if sudo_prefix:
            rm_result = subprocess.run(
                ["sudo", "rm", "-f", str(plist_path)],  # noqa: S603, S607
                capture_output=True,
                timeout=10,
            )
            if rm_result.returncode != 0:
                return False, "Failed to remove plist file."
        else:
            try:
                plist_path.unlink()
            except OSError as e:
                return False, f"Failed to remove plist file: {e}"

        if result.returncode != 0:
            stderr = result.stderr.strip()
            return False, f"Removed plist but launchctl unload failed: {stderr}"

        return True, f"Uninstalled launchd plist for '{name}'."

    # ------------------------------------------------------------------------------------
    def install_all_services(self) -> list[tuple[str, bool, str]]:
        """Install launchd plists for all running processes."""
        processes = load_state()
        results: list[tuple[str, bool, str]] = []

        for name, entry in processes.items():
            if entry.status == "running":
                ok, msg = self.install_service(entry)
                results.append((name, ok, msg))

        return results

    # ------------------------------------------------------------------------------------
    def is_service_installed(self, name: str) -> bool:
        """Check if a launchd plist is installed for a process (agent or daemon)."""
        return (
            _plist_path(name, sudo=False).exists()
            or _plist_path(name, sudo=True).exists()
        )

    # ------------------------------------------------------------------------------------
    def get_service_pid(self, name: str, sudo: bool = False) -> int:
        """Query launchd for the PID of a managed process. Returns 0 if not running."""
        label = _plist_label(name)
        # Use sudo -n (non-interactive) to avoid password prompts in read-only operations
        sudo_prefix: list[str] = ["sudo", "-n"] if sudo else []

        try:
            result = subprocess.run(
                [*sudo_prefix, "launchctl", "list"],  # noqa: S603, S607
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return 0

        if result.returncode != 0:
            return 0

        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[2] == label:
                try:
                    pid = int(parts[0])
                    return pid if pid > 0 else 0
                except ValueError:
                    return 0

        return 0


# ----------------------------------------------------------------------------------------
#   Private Helpers
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def _plist_label(name: str) -> str:
    """Return the launchd label for a process."""
    return f"{PLIST_PREFIX}.{name}"


# ----------------------------------------------------------------------------------------
def _plist_path(name: str, sudo: bool = False) -> Path:
    """Return the plist file path for a process."""
    base = LAUNCH_DAEMONS_DIR if sudo else LAUNCH_AGENTS_DIR
    return base / f"{_plist_label(name)}.plist"


# ----------------------------------------------------------------------------------------
def _generate_plist(entry: ProcessEntry) -> bytes:
    """Generate a launchd plist for a process entry."""
    log_path = str(get_log_path(entry.name))

    # For sudo processes, the plist goes in LaunchDaemons (runs as root),
    # so the command does not need a sudo prefix.
    wrapped = wrap_command(entry.command)

    plist_dict: dict[str, object] = {
        "Label": _plist_label(entry.name),
        "ProgramArguments": ["/bin/sh", "-c", wrapped],
        "WorkingDirectory": entry.cwd,
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
        "KeepAlive": True,
        "RunAtLoad": True,
    }

    if entry.env:
        plist_dict["EnvironmentVariables"] = entry.env

    return plistlib.dumps(plist_dict)
