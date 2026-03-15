# ----------------------------------------------------------------------------------------
#   macpmd
#   -----
#
#   Process manager — a PM2 equivalent using launchd/systemd for persistence.
#
#   (c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
#
#   Version History
#   ---------------
#   Mar 2026 - Created
# ----------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------
#   Version
# ----------------------------------------------------------------------------------------

from .version import VERSION_STR

__version__ = VERSION_STR
__all__ = ["__version__"]
