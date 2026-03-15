# ----------------------------------------------------------------------------------------
#   backend.py
#   ----------
#
#   Service backend abstraction. Defines the interface for platform-specific service
#   managers (launchd on macOS, systemd on Linux) and provides a factory function
#   to select the correct backend at runtime.
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

import sys
from abc import ABC
from abc import abstractmethod
from .state import ProcessEntry

# ----------------------------------------------------------------------------------------
#   Backend Interface
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
class ServiceBackend(ABC):
    """Abstract base class for platform-specific service backends.

    Each backend provides methods to install, uninstall, and query service files
    that give processes boot persistence and crash recovery.
    """

    @abstractmethod
    def install_service(self, entry: ProcessEntry) -> tuple[bool, str]:
        """Install a service file for a process. Returns (success, message)."""

    @abstractmethod
    def uninstall_service(self, name: str, sudo: bool = False) -> tuple[bool, str]:
        """Uninstall a service file for a process. Returns (success, message)."""

    @abstractmethod
    def install_all_services(self) -> list[tuple[str, bool, str]]:
        """Install service files for all running processes."""

    @abstractmethod
    def is_service_installed(self, name: str) -> bool:
        """Check if a service file is installed for a process."""

    @abstractmethod
    def get_service_pid(self, name: str, sudo: bool = False) -> int:
        """Query the service manager for the PID of a process. Returns 0 if not found."""

    @abstractmethod
    def service_label(self) -> str:
        """Return a display label for this backend (e.g. 'launchd', 'systemd')."""


# ----------------------------------------------------------------------------------------
#   Factory
# ----------------------------------------------------------------------------------------

_backend: ServiceBackend | None = None


# ----------------------------------------------------------------------------------------
def get_backend() -> ServiceBackend:
    """Return the service backend for the current platform (cached singleton)."""
    global _backend  # noqa: PLW0603

    if _backend is not None:
        return _backend

    if sys.platform == "darwin":
        from .backend_launchd import LaunchdBackend

        _backend = LaunchdBackend()
    elif sys.platform == "linux":
        from .backend_systemd import SystemdBackend

        _backend = SystemdBackend()
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")

    return _backend
