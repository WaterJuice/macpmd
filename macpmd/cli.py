# ----------------------------------------------------------------------------------------
#   cli.py
#   ------
#
#   CLI argument parsing and subcommand handlers. Provides commands for adding,
#   starting, stopping, restarting, deleting, listing processes, viewing logs,
#   and setting up launchd persistence.
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
import subprocess
import sys
import traceback
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from pathlib import PurePosixPath
from .argbuilder import ArgsParser
from .argbuilder import Namespace
from .colour import bold
from .colour import cyan
from .colour import dim
from .colour import green
from .colour import red
from .colour import yellow
from .launchd import install_plist
from .launchd import is_plist_installed
from .launchd import uninstall_plist
from .logs import delete_logs
from .logs import follow_log
from .logs import follow_logs_all
from .logs import prefix_log_lines
from .logs import tail_log
from .process import is_process_alive
from .process import refresh_all_statuses
from .process import restart_process
from .process import start_process
from .process import stop_process
from .state import ProcessEntry
from .state import get_process
from .state import load_state
from .state import remove_process
from .version import VERSION_STR

# ----------------------------------------------------------------------------------------
#   Constants
# ----------------------------------------------------------------------------------------

_COL_NAME = 16
_COL_STATUS = 12
_COL_PID = 10
_COL_UPTIME = 16
_COL_RESTARTS = 10
_COL_SUDO = 8
_COL_LAUNCHD = 10

# Type alias for subcommand handler functions.
_CommandHandler = Callable[[Namespace], int]

# Interpreters whose name should be skipped when deriving a process name.
_INTERPRETERS = frozenset(
    {
        "bash",
        "sh",
        "zsh",
        "fish",
        "dash",
        "ksh",
        "csh",
        "tcsh",
        "python",
        "python3",
        "python2",
        "node",
        "deno",
        "bun",
        "ruby",
        "perl",
        "php",
        "java",
        "kotlin",
        "scala",
        "go",
        "cargo",
        "rustc",
    }
)

_LICENCE_TEXT = """\
macpmd — Released under the Unlicense (public domain)

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

For more information, please refer to <https://unlicense.org/>
"""

# ----------------------------------------------------------------------------------------
#   Argument Parser
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def _create_parser() -> ArgsParser:
    """Build the argument parser with subcommands."""
    parser = ArgsParser(
        prog="macpmd",
        description="macOS process manager using launchd for persistence.",
        version=f"macpmd: {VERSION_STR}\npython: {sys.version.split()[0]}",
    )

    # Top-level options -------------------------------------------------------
    parser.add_argument(
        "--license",
        action="store_true",
        dest="license",
        help="Show license information and exit",
    )

    # add --------------------------------------------------------------------
    add_cmd = parser.add_command(
        "add",
        help="Register and start a new process",
    )
    add_cmd.add_argument(
        "cmd",
        metavar="COMMAND",
        help="The command to run (e.g. 'node server.js')",
    )
    add_cmd.add_argument(
        "--name",
        "-n",
        metavar="NAME",
        help="Name for the process (auto-derived from command if omitted)",
    )
    add_cmd.add_argument(
        "--sudo",
        "-s",
        action="store_true",
        help="Run the process with sudo",
    )

    # start ------------------------------------------------------------------
    start_cmd = parser.add_command(
        "start",
        help="Start one or more stopped/errored processes",
    )
    start_cmd.add_argument(
        "names",
        nargs="*",
        metavar="NAME",
        help="Names of the processes to start",
    )
    start_cmd.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="all_processes",
        help="Start all stopped/errored processes",
    )

    # stop -------------------------------------------------------------------
    stop_cmd = parser.add_command(
        "stop",
        help="Stop one or more running processes",
    )
    stop_cmd.add_argument(
        "names",
        nargs="*",
        metavar="NAME",
        help="Names of the processes to stop",
    )
    stop_cmd.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="all_processes",
        help="Stop all processes",
    )

    # restart ----------------------------------------------------------------
    restart_cmd = parser.add_command(
        "restart",
        help="Restart one or more processes",
    )
    restart_cmd.add_argument(
        "names",
        nargs="*",
        metavar="NAME",
        help="Names of the processes to restart",
    )
    restart_cmd.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="all_processes",
        help="Restart all processes",
    )

    # delete -----------------------------------------------------------------
    delete_cmd = parser.add_command(
        "delete",
        help="Remove one or more processes from macpmd (stops first if running)",
    )
    delete_cmd.add_argument(
        "names",
        nargs="*",
        metavar="NAME",
        help="Names of the processes to delete",
    )
    delete_cmd.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="all_processes",
        help="Delete all processes",
    )

    # list -------------------------------------------------------------------
    parser.add_command(
        "list",
        help="Show all processes with status, PID, uptime, and restarts",
    )

    # logs -------------------------------------------------------------------
    logs_cmd = parser.add_command(
        "logs",
        help="Tail logs for a process (or all processes with --all)",
    )
    logs_cmd.add_argument(
        "names",
        nargs="*",
        metavar="NAME",
        help="Names of the processes",
    )
    logs_cmd.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="all_processes",
        help="Show logs for all processes",
    )
    logs_cmd.add_argument(
        "--lines",
        "-l",
        type=int,
        default=50,
        metavar="N",
        help="Number of lines to show (default: 50, 0 for all)",
    )
    logs_cmd.add_argument(
        "--follow",
        "-f",
        action="store_true",
        help="Follow log output in real-time",
    )

    return parser


# ----------------------------------------------------------------------------------------
#   Helpers
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def _format_uptime(started_at: str) -> str:
    """Format a human-readable uptime string from an ISO timestamp."""
    if not started_at:
        return "-"
    try:
        start = datetime.fromisoformat(started_at)
        now = datetime.now(UTC)
        delta = now - start
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return "-"
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
    except (ValueError, TypeError):
        return "-"


# ----------------------------------------------------------------------------------------
def _status_colour(status: str) -> str:
    """Return a coloured status string."""
    if status == "running":
        return green(status)
    if status == "errored":
        return red(status)
    return dim(status)


# ----------------------------------------------------------------------------------------
def _resolve_names(args: Namespace, verb: str) -> list[str] | None:
    """Resolve process names from positional args or --all. Returns None on error."""
    all_flag: bool = args.all_processes
    names: list[str] = args.names

    if all_flag and names:
        print(red("Cannot specify both names and --all."), file=sys.stderr)
        return None

    if all_flag:
        processes = load_state()
        if not processes:
            print(dim("No processes registered."))
            return []
        return sorted(processes)

    if not names:
        print(
            red(f"Specify one or more process names, or use --all to {verb} all."),
            file=sys.stderr,
        )
        return None

    return names


# ----------------------------------------------------------------------------------------
def _derive_name(command: str) -> str:
    """Derive a process name from a shell command.

    Takes the first meaningful token (skipping interpreters), strips the path
    and extension, and sanitises to alphanumeric characters and hyphens.
    """
    tokens = command.split()
    if not tokens:
        return "process"

    # Pick the first token, but skip known interpreters
    candidate = tokens[0]
    basename = PurePosixPath(candidate).stem
    if basename in _INTERPRETERS and len(tokens) > 1:
        candidate = tokens[1]
        # Skip interpreter flags like -u, -m, --flag
        idx = 1
        while idx < len(tokens) and tokens[idx].startswith("-"):
            idx += 1
        if idx < len(tokens):
            candidate = tokens[idx]

    # Strip path and extension
    name = PurePosixPath(candidate).stem

    # Sanitise: keep only alphanumeric, hyphens, underscores
    name = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")

    return name if name else "process"


# ----------------------------------------------------------------------------------------
def _unique_name(base_name: str) -> str:
    """Return a unique process name, appending -2, -3 etc. if needed."""
    processes = load_state()
    if base_name not in processes:
        return base_name
    n = 2
    while f"{base_name}-{n}" in processes:
        n += 1
    return f"{base_name}-{n}"


# ----------------------------------------------------------------------------------------
def _ensure_sudo() -> bool:
    """Ensure sudo credentials are available. Returns True on success."""
    check = subprocess.run(
        ["sudo", "-n", "true"],  # noqa: S603, S607
        capture_output=True,
        timeout=10,
    )
    if check.returncode == 0:
        return True
    print(dim("sudo credentials required for this operation."))
    result = subprocess.run(
        ["sudo", "-v"],  # noqa: S603, S607
        timeout=60,
    )
    return result.returncode == 0


# ----------------------------------------------------------------------------------------
#   Subcommand Handlers
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def _cmd_add(args: Namespace) -> int:
    """Register and start a new process."""
    command: str = args.cmd
    use_sudo: bool = args.sudo

    # Derive or validate name
    name: str | None = args.name
    if name:
        existing = get_process(name)
        if (
            existing is not None
            and existing.status == "running"
            and is_process_alive(existing.pid)
        ):
            print(yellow(f"Process '{name}' is already running (PID {existing.pid})."))
            return 0
    else:
        name = _unique_name(_derive_name(command))

    cwd = os.getcwd()
    env = dict(os.environ)

    existing = get_process(name)
    entry = ProcessEntry(
        name=name,
        command=command,
        cwd=cwd,
        env=env,
        sudo=use_sudo,
        restarts=existing.restarts if existing is not None else 0,
    )

    # For sudo processes, validate credentials interactively before backgrounding
    if use_sudo:
        if not _ensure_sudo():
            print(red("Failed to obtain sudo credentials."), file=sys.stderr)
            return 1

    ok, msg = start_process(entry)
    if not ok:
        print(red(msg), file=sys.stderr)
        return 1

    print(green(msg))

    # Install launchd plist for boot persistence and crash recovery
    plist_ok, plist_msg = install_plist(entry)
    if plist_ok:
        print(dim(plist_msg))
    else:
        print(yellow(f"Warning: {plist_msg}"), file=sys.stderr)

    return 0


# ----------------------------------------------------------------------------------------
def _cmd_start(args: Namespace) -> int:
    """Start one or more stopped/errored processes."""
    names = _resolve_names(args, "start")
    if names is None:
        return 1
    if not names:
        return 0

    if not _ensure_sudo_for_entries(names):
        print(red("Failed to obtain sudo credentials."), file=sys.stderr)
        return 1

    rc = 0
    for name in names:
        entry = get_process(name)
        if entry is None:
            print(red(f"Process '{name}' not found."), file=sys.stderr)
            rc = 1
            continue

        if entry.status == "running" and is_process_alive(entry.pid):
            print(yellow(f"Process '{name}' is already running (PID {entry.pid})."))
            continue

        # For sudo processes, validate credentials
        if entry.sudo:
            if not _ensure_sudo():
                print(red("Failed to obtain sudo credentials."), file=sys.stderr)
                rc = 1
                continue

        ok, msg = start_process(entry)
        if not ok:
            print(red(msg), file=sys.stderr)
            rc = 1
            continue

        print(green(msg))

        # Install launchd plist for boot persistence and crash recovery
        plist_ok, plist_msg = install_plist(entry)
        if plist_ok:
            print(dim(plist_msg))
        else:
            print(yellow(f"Warning: {plist_msg}"), file=sys.stderr)

    return rc


# ----------------------------------------------------------------------------------------
def _ensure_sudo_for_entries(names: list[str]) -> bool:
    """If any of the named processes use sudo, ensure credentials are available."""
    for name in names:
        entry = get_process(name)
        if entry is not None and entry.sudo:
            return _ensure_sudo()
    return True


# ----------------------------------------------------------------------------------------
def _cmd_stop(args: Namespace) -> int:
    """Stop one or more running processes."""
    names = _resolve_names(args, "stop")
    if names is None:
        return 1
    if not names:
        return 0

    if not _ensure_sudo_for_entries(names):
        print(red("Failed to obtain sudo credentials."), file=sys.stderr)
        return 1

    rc = 0
    for name in names:
        entry = get_process(name)
        if entry is None:
            print(red(f"Process '{name}' not found."), file=sys.stderr)
            rc = 1
            continue

        # Uninstall launchd plist first so launchd does not restart the process
        if is_plist_installed(name):
            uninstall_plist(name, sudo=entry.sudo)

        ok, msg = stop_process(entry)
        if ok:
            print(green(msg))
        else:
            print(red(msg), file=sys.stderr)
            rc = 1

    return rc


# ----------------------------------------------------------------------------------------
def _cmd_restart(args: Namespace) -> int:
    """Restart one or more processes."""
    names = _resolve_names(args, "restart")
    if names is None:
        return 1
    if not names:
        return 0

    if not _ensure_sudo_for_entries(names):
        print(red("Failed to obtain sudo credentials."), file=sys.stderr)
        return 1

    rc = 0
    for name in names:
        entry = get_process(name)
        if entry is None:
            print(red(f"Process '{name}' not found."), file=sys.stderr)
            rc = 1
            continue

        # Uninstall plist before stopping so launchd does not interfere
        if is_plist_installed(name):
            uninstall_plist(name, sudo=entry.sudo)

        ok, msg = restart_process(entry)
        if not ok:
            print(red(msg), file=sys.stderr)
            rc = 1
            continue

        print(green(msg))

        # Reinstall launchd plist with updated state
        plist_ok, plist_msg = install_plist(entry)
        if plist_ok:
            print(dim(plist_msg))
        else:
            print(yellow(f"Warning: {plist_msg}"), file=sys.stderr)

    return rc


# ----------------------------------------------------------------------------------------
def _cmd_delete(args: Namespace) -> int:
    """Remove one or more processes from macpmd (stops first if running)."""
    names = _resolve_names(args, "delete")
    if names is None:
        return 1
    if not names:
        return 0

    if not _ensure_sudo_for_entries(names):
        print(red("Failed to obtain sudo credentials."), file=sys.stderr)
        return 1

    rc = 0
    for name in names:
        entry = get_process(name)
        if entry is None:
            print(red(f"Process '{name}' not found."), file=sys.stderr)
            rc = 1
            continue

        # Stop if running
        if entry.status == "running" and is_process_alive(entry.pid):
            stop_process(entry)

        # Uninstall launchd plist if present
        if is_plist_installed(name):
            uninstall_plist(name, sudo=entry.sudo)

        # Delete logs
        delete_logs(name)

        # Remove from state
        remove_process(name)
        print(green(f"Process '{name}' deleted."))

    return rc


# ----------------------------------------------------------------------------------------
def _cmd_list(_args: Namespace) -> int:
    """Show all processes with status, PID, uptime, and restarts."""
    processes = refresh_all_statuses()

    if not processes:
        print(dim("No processes registered."))
        return 0

    # Table header
    hdr = (
        f"{'Name':<{_COL_NAME}}"
        f"{'Status':<{_COL_STATUS}}"
        f"{'PID':<{_COL_PID}}"
        f"{'Uptime':<{_COL_UPTIME}}"
        f"{'Restarts':<{_COL_RESTARTS}}"
        f"{'Sudo':<{_COL_SUDO}}"
        f"{'launchd':<{_COL_LAUNCHD}}"
    )
    print(bold(hdr))
    total_width = (
        _COL_NAME
        + _COL_STATUS
        + _COL_PID
        + _COL_UPTIME
        + _COL_RESTARTS
        + _COL_SUDO
        + _COL_LAUNCHD
    )
    print(dim("-" * total_width))

    for name, entry in sorted(processes.items()):
        # Truncate long names
        display_name = name
        max_name = _COL_NAME - 1
        if len(display_name) > max_name:
            display_name = display_name[: max_name - 1] + "\u2026"

        pid_str = str(entry.pid) if entry.pid > 0 else "-"
        uptime_str = (
            _format_uptime(entry.started_at) if entry.status == "running" else "-"
        )
        restarts_str = str(entry.restarts)
        sudo_str = "yes" if entry.sudo else "no"
        launchd_str = green("yes") if is_plist_installed(name) else dim("no")

        # Pad plain text before colourising
        status_plain = entry.status
        col_name = cyan(display_name.ljust(_COL_NAME))
        col_status = _status_colour(status_plain) + " " * max(
            0, _COL_STATUS - len(status_plain)
        )
        col_pid = dim(pid_str.ljust(_COL_PID))
        col_uptime = dim(uptime_str.ljust(_COL_UPTIME))
        col_restarts = dim(restarts_str.ljust(_COL_RESTARTS))
        col_sudo = (
            yellow(sudo_str.ljust(_COL_SUDO))
            if entry.sudo
            else dim(sudo_str.ljust(_COL_SUDO))
        )
        col_launchd = launchd_str

        print(
            f"{col_name}{col_status}{col_pid}{col_uptime}{col_restarts}{col_sudo}{col_launchd}"
        )

    return 0


# ----------------------------------------------------------------------------------------
def _cmd_logs(args: Namespace) -> int:
    """Tail logs for one or more processes, or all with --all."""
    all_processes: bool = args.all_processes
    names_arg: list[str] = args.names
    lines: int = args.lines
    follow: bool = args.follow

    if all_processes and names_arg:
        print(red("Cannot specify both names and --all."), file=sys.stderr)
        return 1

    if all_processes:
        processes = load_state()
        if not processes:
            print(dim("No processes registered."))
            return 0
        names = sorted(processes)
    elif names_arg:
        names = names_arg
        # Validate all names exist
        for name in names:
            if get_process(name) is None:
                print(red(f"Process '{name}' not found."), file=sys.stderr)
                return 1
    else:
        print(
            red("Specify one or more process names, or use --all for all processes."),
            file=sys.stderr,
        )
        return 1

    # Single process: no prefix
    if len(names) == 1:
        name = names[0]
        if follow:
            output = tail_log(name, lines)
            if output:
                print(output)
            print(dim(f"Following logs for '{name}' (Ctrl+C to stop)..."))
            try:
                follow_log(name)
            except KeyboardInterrupt:
                pass
        else:
            output = tail_log(name, lines)
            print(output)
        return 0

    # Multiple processes: prefix with coloured name
    if follow:
        for i, name in enumerate(names):
            output = tail_log(name, lines)
            if output:
                print(prefix_log_lines(name, output, i))
        print(dim("Following logs for all processes (Ctrl+C to stop)..."))
        try:
            follow_logs_all(names)
        except KeyboardInterrupt:
            pass
        return 0

    for i, name in enumerate(names):
        output = tail_log(name, lines)
        if output:
            print(prefix_log_lines(name, output, i))
        else:
            print(prefix_log_lines(name, dim("(no output)"), i))
        print()

    return 0


# ----------------------------------------------------------------------------------------
#   Main Entry Point
# ----------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------
def main() -> int:
    """Entry point: parse arguments and dispatch to subcommand."""
    if sys.platform != "darwin":
        print("macpmd requires macOS.", file=sys.stderr)
        return 1

    try:
        return _main_inner()
    except KeyboardInterrupt:
        return 0
    except SystemExit:
        raise
    except BaseException as e:
        t = "-------------------------------------------------------------------\n"
        t += "UNHANDLED EXCEPTION OCCURRED!!\n"
        t += "\n"
        t += traceback.format_exc()
        t += "\n"
        t += f"EXCEPTION: {type(e)} {e}\n"
        t += "-------------------------------------------------------------------\n"
        print(t, file=sys.stderr)
        return 1


# ----------------------------------------------------------------------------------------
def _main_inner() -> int:
    """Inner main function that does the actual work."""
    # Handle --license before parsing (no command needed).
    if "--license" in sys.argv:
        print(_LICENCE_TEXT)
        return 0

    parser = _create_parser()
    args: Namespace = parser.parse()

    commands: dict[str, _CommandHandler] = {
        "add": _cmd_add,
        "start": _cmd_start,
        "stop": _cmd_stop,
        "restart": _cmd_restart,
        "delete": _cmd_delete,
        "list": _cmd_list,
        "logs": _cmd_logs,
    }

    return commands[args.command](args)
