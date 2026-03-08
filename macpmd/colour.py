# ----------------------------------------------------------------------------------------
#   colour.py
#   ---------
#
#   ANSI colour output for terminal. Only applies colours when stdout is a TTY
#   and colours are not disabled.
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

# ----------------------------------------------------------------------------------------
#   ANSI Codes
# ----------------------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

# Colours that are readable on both light and dark terminal backgrounds.
# Avoids white, black, and bright variants that wash out on one or the other.
_LOG_COLOURS = [CYAN, MAGENTA, GREEN, YELLOW, BLUE, RED]

# ----------------------------------------------------------------------------------------
#   State
# ----------------------------------------------------------------------------------------

_colours_enabled: bool | None = None

# ----------------------------------------------------------------------------------------
#   Functions
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def set_colours_enabled(enabled: bool) -> None:
    """Explicitly enable or disable colours."""
    global _colours_enabled
    _colours_enabled = enabled


# ----------------------------------------------------------------------------------------
def _should_use_colours() -> bool:
    """Determine if colours should be used."""
    global _colours_enabled

    # If explicitly set, use that
    if _colours_enabled is not None:
        return _colours_enabled

    # Auto-detect: use colours if stdout is a TTY
    return sys.stdout.isatty()


# ----------------------------------------------------------------------------------------
def green(text: str) -> str:
    """Return text in green (for success)."""
    if _should_use_colours():
        return f"{GREEN}{text}{RESET}"
    return text


# ----------------------------------------------------------------------------------------
def yellow(text: str) -> str:
    """Return text in yellow (for warning)."""
    if _should_use_colours():
        return f"{YELLOW}{text}{RESET}"
    return text


# ----------------------------------------------------------------------------------------
def red(text: str) -> str:
    """Return text in red (for error)."""
    if _should_use_colours():
        return f"{RED}{text}{RESET}"
    return text


# ----------------------------------------------------------------------------------------
def cyan(text: str) -> str:
    """Return text in cyan (for info)."""
    if _should_use_colours():
        return f"{CYAN}{text}{RESET}"
    return text


# ----------------------------------------------------------------------------------------
def bold(text: str) -> str:
    """Return text in bold."""
    if _should_use_colours():
        return f"{BOLD}{text}{RESET}"
    return text


# ----------------------------------------------------------------------------------------
def dim(text: str) -> str:
    """Return text in dim (for secondary info)."""
    if _should_use_colours():
        return f"{DIM}{text}{RESET}"
    return text


# ----------------------------------------------------------------------------------------
def colourise(text: str, index: int) -> str:
    """Return text coloured by cycling through the log colour palette."""
    if _should_use_colours():
        code = _LOG_COLOURS[index % len(_LOG_COLOURS)]
        return f"{code}{text}{RESET}"
    return text
