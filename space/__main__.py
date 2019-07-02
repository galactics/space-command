#!/usr/bin/env python

"""Space Command, a command for space application
"""

import os
import sys
import logging
from pkg_resources import iter_entry_points

from . import __version__
from .utils import docopt
from .wspace import ws

log = logging.getLogger(__package__)


def pm_on_crash(type, value, tb):
    """Exception hook, in order to start pdb when an exception occurs
    """
    import pdb
    import traceback
    traceback.print_exception(type, value, tb)
    pdb.pm()


def log_on_crash(type, value, tb):
    """Uncaught exceptions handler
    """
    log.exception(value, exc_info=(type, value, tb))
    # sys.__excepthook__(type, value, tb)


def get_doc(func):
    return func.__doc__.splitlines()[0] if func.__doc__ is not None else ""


def main():
    """Direct the user to the right subcommand
    """

    if '--pdb' in sys.argv:
        sys.argv.remove('--pdb')
        func = pm_on_crash
    else:
        func = log_on_crash

    sys.excepthook = func

    if "--version" in sys.argv:
        import beyond

        print("space-command  {}".format(__version__))
        print("beyond         {}".format(beyond.__version__))
        sys.exit(0)

    # Set logging verbosity level.
    # This setting will be overridden when loading the workspace (see `ws.init()` below)
    # but it allow to have a crude logging of all the initialization process.
    if "-v" in sys.argv or "--verbose" in sys.argv:

        if "-v" in sys.argv:
            sys.argv.remove('-v')
        else:
            sys.argv.remove('--verbose')

        verbose = True
        logging.basicConfig(level=logging.DEBUG, format='%(message)s')
        log.debug("Verbose mode activated")
    else:
        verbose = False
        logging.basicConfig(level=logging.INFO, format='%(message)s')

    # Retrieve the workspace if defined both as a command argument or as a
    # environment variable. The command line argument takes precedence
    if "-w" in sys.argv or '--workspace' in sys.argv:
        idx = sys.argv.index('-w') if "-w" in sys.argv else sys.argv.index('--workspace')
        sys.argv.pop(idx)
        ws.name = sys.argv.pop(idx)
    elif 'SPACE_WORKSPACE' in os.environ:
        ws.name = os.environ['SPACE_WORKSPACE']

    log.debug("workspace '{}'".format(ws.name))

    # List of available subcommands
    commands = {entry.name: entry for entry in iter_entry_points('space.commands')}

    if len(sys.argv) <= 1 or sys.argv[1] not in commands:
        # No or wrong subcommand

        helper = "Available sub-commands :\n"
        addons = ""
        for name, entry in sorted(commands.items()):
            cmd = entry.load()
            if entry.dist.project_name == "space-command":
                helper += " {:<10} {}\n".format(name, get_doc(cmd))
            else:
                addons += " {:<10} {}\n".format(name, get_doc(cmd))

        print(__doc__)
        print(helper)

        if addons:
            print("Available addons sub-commands :")
            print(addons)

        print("Options :")
        print(" --pdb                   Launch the python debugger when an exception is raised")
        print(" --version               Show the version of the space-command utility")
        print(" -v, --verbose           Show DEBUG level messages")
        print(" -w, --workspace <name>  Select the workspace to use")
        print()
        print("To list, create and delete workspaces, use the companion command 'wspace'")
        print()
        sys.exit(-1)

    # retrieve the subcommand and its arguments
    _, command, *args = sys.argv

    ws.config.verbose = verbose

    # Before loading the workspace, no file logging is initialized, so any logging will
    # only be reported on console thanks to the `logging.basicConfig()` above
    try:
        ws.load()
    except FileNotFoundError:
        log.error("It seems you are running 'space' for the first time")
        log.error("To initialize the workspace '{}', please use the command 'wspace'".format(ws.name))
        sys.exit(-1)

    log.debug("=== starting subcommand '{}' ===".format(command))

    # get the function associated with the subcommand
    func = commands[command].load()

    # Call the function associated with the subcommand
    func(*args)


if __name__ == "__main__":
    main()
