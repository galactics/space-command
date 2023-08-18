#!/usr/bin/env python

"""Space Command, a command for space application
"""

import os
import sys
import logging
from docopt import DocoptExit

if sys.version_info.minor >= 8:
    from importlib.metadata import entry_points as vanilla_entry_points

    if sys.version_info.minor >= 10:
        entry_points = vanilla_entry_points
    else:
        # Creating a custom filtering function to circumvent the lack of filtering
        # of the entry_points function in python 3.8 and 3.9
        def entry_points(group=None):
            entries = vanilla_entry_points()
            if group:
                entries = entries[group]
            return entries

else:
    from pkg_resources import iter_entry_points

    entry_points = lambda group=None: iter_entry_points(group)

import beyond

from . import __version__
from .wspace import ws

log = logging.getLogger(__package__)


def list_subcommands():
    subcommands = {}
    for entry in entry_points(group="space.commands"):
        subcommands[entry.name] = entry.load
    return subcommands


def pm_on_crash(type, value, tb):
    """Exception hook, in order to start pdb when an exception occurs"""
    import pdb
    import traceback

    traceback.print_exception(type, value, tb)
    pdb.pm()


def log_on_crash(type, value, tb):
    """Uncaught exceptions handler"""
    log.exception(value, exc_info=(type, value, tb))
    # sys.__excepthook__(type, value, tb)


def get_doc(func):
    return func.__doc__.splitlines()[0] if func.__doc__ is not None else ""


def main():
    """Direct the user to the right subcommand"""

    if "--pdb" in sys.argv:
        sys.argv.remove("--pdb")
        func = pm_on_crash
    else:
        func = log_on_crash

    sys.excepthook = func

    if "--version" in sys.argv:
        print("space-command  {}".format(__version__))
        print("beyond         {}".format(beyond.__version__))
        sys.exit(127)

    # Set logging verbosity level.
    # This setting will be overridden when loading the workspace (see `ws.init()` below)
    # but it allow to have a crude logging of all the initialization process.
    if "-v" in sys.argv or "--verbose" in sys.argv:
        if "-v" in sys.argv:
            sys.argv.remove("-v")
        else:
            sys.argv.remove("--verbose")

        verbose = True
        logging.basicConfig(level=logging.DEBUG, format="%(message)s")
        log.debug("Verbose mode activated")
    else:
        verbose = False
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    colors = True
    if "--no-color" in sys.argv:
        log.debug("Disable colors on logging")
        colors = False
        sys.argv.remove("--no-color")

    # Retrieve the workspace if defined both as a command argument or as a
    # environment variable. The command line argument takes precedence
    if "-w" in sys.argv or "--workspace" in sys.argv:
        idx = (
            sys.argv.index("-w") if "-w" in sys.argv else sys.argv.index("--workspace")
        )
        sys.argv.pop(idx)
        ws.name = sys.argv.pop(idx)
    elif "SPACE_WORKSPACE" in os.environ:
        ws.name = os.environ["SPACE_WORKSPACE"]

    log.debug("workspace '{}'".format(ws.name))

    # List of available subcommands
    commands = list_subcommands()

    if len(sys.argv) <= 1 or sys.argv[1] not in commands:
        # No or wrong subcommand

        helper = "Available sub-commands :\n"
        addons = ""

        _max = len(max(commands.keys(), key=len))

        for name, func_loader in sorted(commands.items()):
            helper += " {:<{}}  {}\n".format(name, _max, get_doc(func_loader()))

        print(__doc__)
        print(helper)

        print("Options :")
        print(
            " --pdb                   Launch the python debugger when an exception is raised"
        )
        print(" --version               Show the version of the space-command utility")
        print(" -v, --verbose           Show DEBUG level messages")
        print(" -w, --workspace <name>  Select the workspace to use")
        print(" --no-color              Disable colored output")
        print()
        print(
            "To list, create and delete workspaces, use the companion command 'wspace'"
        )
        print()
        sys.exit(1)

    # retrieve the subcommand and its arguments
    _, command, *args = sys.argv

    if command == "log":
        # disable logging when using the log command
        ws.config["logging"] = {}
    ws.config.verbose = verbose
    ws.config.colors = colors

    # Before loading the workspace, no file logging is initialized, so any logging will
    # only be reported on console thanks to the `logging.basicConfig()` above
    try:
        ws.load()
    except FileNotFoundError:
        log.error("It seems you are running 'space' for the first time")
        log.error(
            "To initialize the workspace '{}', please use the command 'wspace'".format(
                ws.name
            )
        )
        sys.exit(1)

    log.debug("=== starting command '{}' ===".format(command))
    log.debug(f"beyond {beyond.__version__} / space {__version__}")
    log.debug(f"args : space {command} {' '.join(args)}")

    # get the function associated with the subcommand
    func = commands[command]()

    try:
        # Call the function associated with the subcommand
        func(*args)
    except DocoptExit as e:
        # Docopt override the SystemExit exception with its own subclass, and
        # pass a string containing the usage of the command as argument.
        # This benefit from the behavior of the SystemExit exception which
        # when not catched, print any non-integer argument and exit with code 1

        # So we have to catch the DocoptExit in order to modify the return code
        # and override it with a decent value.
        print(e, file=sys.stderr)
        log.debug(f"=== command '{command}' failed with return code 2 ===")
        sys.exit(2)
    except SystemExit as e:
        log.debug(f"=== command '{command}' failed with return code {e.code} ===")
        raise
    else:
        log.debug(f"=== command '{command}' exited with return code 0 ===")


if __name__ == "__main__":
    main()
