# ----------------------------------------------------------------------------------------
#   backend_systemd.py
#   ------------------
#
#   systemd service backend for Linux. Generates and manages unit files in
#   ~/.config/systemd/user/ (user services) and /etc/systemd/system/ (system
#   services) for boot persistence and crash recovery via Restart=always.
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

USER_UNITS_DIR = Path.home() / ".config" / "systemd" / "user"
SYSTEM_UNITS_DIR = Path("/etc/systemd/system")
SERVICE_PREFIX = "macpmd"

# ----------------------------------------------------------------------------------------
#   Backend
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
class SystemdBackend(ServiceBackend):
    """Linux systemd service backend."""

    # ------------------------------------------------------------------------------------
    def service_label(self) -> str:
        """Return the display label for this backend."""
        return "systemd"

    # ------------------------------------------------------------------------------------
    def install_service(self, entry: ProcessEntry) -> tuple[bool, str]:
        """Generate and install a systemd unit file for a process."""
        use_sudo = entry.sudo
        unit_path = _unit_path(entry.name, sudo=use_sudo)
        unit_content = _generate_unit(entry)

        if use_sudo:
            SYSTEM_UNITS_DIR.mkdir(parents=True, exist_ok=True)
        else:
            USER_UNITS_DIR.mkdir(parents=True, exist_ok=True)

        # Stop existing service if active
        service_name = _service_name(entry.name)
        _systemctl(["stop", service_name], sudo=use_sudo, check=False)

        try:
            if use_sudo:
                # Write via sudo tee since we cannot write to /etc/systemd/system directly
                proc = subprocess.run(
                    ["sudo", "tee", str(unit_path)],  # noqa: S603, S607
                    input=unit_content.encode("utf-8"),
                    capture_output=True,
                    timeout=10,
                )
                if proc.returncode != 0:
                    return (
                        False,
                        f"Failed to write unit file: {proc.stderr.decode().strip()}",
                    )
            else:
                unit_path.write_text(unit_content, encoding="utf-8")
        except OSError as e:
            return False, f"Failed to write unit file: {e}"

        # Reload systemd and enable the service
        ok, err = _systemctl(["daemon-reload"], sudo=use_sudo)
        if not ok:
            return False, f"Failed to reload systemd: {err}"

        ok, err = _systemctl(["enable", "--now", service_name], sudo=use_sudo)
        if not ok:
            return False, f"Failed to enable service: {err}"

        return True, f"Installed systemd unit for '{entry.name}'."

    # ------------------------------------------------------------------------------------
    def uninstall_service(self, name: str, sudo: bool = False) -> tuple[bool, str]:
        """Disable and remove a systemd unit file for a process."""
        unit_path = _unit_path(name, sudo=sudo)

        if not unit_path.exists():
            # Check the other location in case sudo flag changed
            alt_path = _unit_path(name, sudo=not sudo)
            if alt_path.exists():
                unit_path = alt_path
                sudo = not sudo
            else:
                return True, f"No systemd unit found for '{name}'."

        service_name = _service_name(name)

        # Disable and stop the service
        _systemctl(["disable", "--now", service_name], sudo=sudo, check=False)

        # Remove the unit file
        if sudo:
            rm_result = subprocess.run(
                ["sudo", "rm", "-f", str(unit_path)],  # noqa: S603, S607
                capture_output=True,
                timeout=10,
            )
            if rm_result.returncode != 0:
                return False, "Failed to remove unit file."
        else:
            try:
                unit_path.unlink()
            except OSError as e:
                return False, f"Failed to remove unit file: {e}"

        # Reload systemd
        _systemctl(["daemon-reload"], sudo=sudo, check=False)

        return True, f"Uninstalled systemd unit for '{name}'."

    # ------------------------------------------------------------------------------------
    def install_all_services(self) -> list[tuple[str, bool, str]]:
        """Install systemd units for all running processes."""
        processes = load_state()
        results: list[tuple[str, bool, str]] = []

        for name, entry in processes.items():
            if entry.status == "running":
                ok, msg = self.install_service(entry)
                results.append((name, ok, msg))

        return results

    # ------------------------------------------------------------------------------------
    def is_service_installed(self, name: str) -> bool:
        """Check if a systemd unit file is installed for a process."""
        return (
            _unit_path(name, sudo=False).exists()
            or _unit_path(name, sudo=True).exists()
        )

    # ------------------------------------------------------------------------------------
    def get_service_pid(self, name: str, sudo: bool = False) -> int:
        """Query systemd for the PID of a managed process. Returns 0 if not running."""
        service_name = _service_name(name)

        cmd: list[str] = ["systemctl"]
        if not sudo:
            cmd.append("--user")
        cmd.extend(["show", "-p", "MainPID", "--value", service_name])

        if sudo:
            cmd = ["sudo", "-n", *cmd]

        try:
            result = subprocess.run(
                cmd,  # noqa: S603
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return 0

        if result.returncode != 0:
            return 0

        try:
            pid = int(result.stdout.strip())
            return pid if pid > 0 else 0
        except ValueError:
            return 0


# ----------------------------------------------------------------------------------------
#   Private Helpers
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def _service_name(name: str) -> str:
    """Return the systemd service name for a process."""
    return f"{SERVICE_PREFIX}-{name}.service"


# ----------------------------------------------------------------------------------------
def _unit_path(name: str, sudo: bool = False) -> Path:
    """Return the unit file path for a process."""
    base = SYSTEM_UNITS_DIR if sudo else USER_UNITS_DIR
    return base / _service_name(name)


# ----------------------------------------------------------------------------------------
def _systemctl(
    args: list[str],
    sudo: bool = False,
    check: bool = True,
) -> tuple[bool, str]:
    """Run a systemctl command. Returns (success, stderr)."""
    cmd: list[str] = []
    if sudo:
        cmd.extend(["sudo"])
    cmd.append("systemctl")
    if not sudo:
        cmd.append("--user")
    cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,  # noqa: S603
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        if check:
            return False, str(e)
        return True, ""

    if result.returncode != 0 and check:
        return False, result.stderr.strip()

    return True, ""


# ----------------------------------------------------------------------------------------
def _generate_unit(entry: ProcessEntry) -> str:
    """Generate a systemd unit file for a process entry."""
    log_path = str(get_log_path(entry.name))
    wrapped = wrap_command(entry.command)

    lines = [
        "[Unit]",
        f"Description=macpmd managed process: {entry.name}",
        "",
        "[Service]",
        "Type=simple",
        f"ExecStart=/bin/sh -c {_shell_escape(wrapped)}",
        f"WorkingDirectory={entry.cwd}",
        "Restart=always",
        "RestartSec=3",
        f"StandardOutput=append:{log_path}",
        f"StandardError=append:{log_path}",
    ]

    if entry.env:
        for key, value in entry.env.items():
            lines.append(f"Environment={_shell_escape(f'{key}={value}')}")

    lines.extend(
        [
            "",
            "[Install]",
            "WantedBy=default.target"
            if not entry.sudo
            else "WantedBy=multi-user.target",
        ]
    )

    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------------------
def _shell_escape(value: str) -> str:
    """Escape a value for use in a systemd unit file.

    Wraps the value in double quotes and escapes backslashes, double quotes,
    and newlines per the systemd.syntax(7) specification.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'
