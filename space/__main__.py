#!/usr/bin/env python

"""Space Command, a command for space application
"""

import os
import sys
import logging
from pkg_resources import iter_entry_points

from . import __version__
from .utils import docopt
from .config import config

log = logging.getLogger(__name__)


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

    verbose = False
    if "-v" in sys.argv or "--verbose" in sys.argv:

        if "-v" in sys.argv:
            sys.argv.remove('-v')
        else:
            sys.argv.remove('--verbose')

        verbose = True

    if "-w" in sys.argv or '--workspace' in sys.argv:
        idx = sys.argv.index('-w') if "-w" in sys.argv else sys.argv.index('--workspace')
        sys.argv.pop(idx)
        workspace = sys.argv.pop(idx)
        config.workspace = workspace
    elif 'SPACE_WORKSPACE' in os.environ:
        config.workspace = os.environ['SPACE_WORKSPACE']

    log.debug("workspace = {}".format(config.workspace))

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
        sys.exit(-1)

    # retrieve the subcommand and its arguments
    _, command, *args = sys.argv
    
    try:
        config.load()
    except FileNotFoundError:
        log.error("It seems you are running 'space' for the first time")
        log.error("To initialize the workspace, please use the command 'wspace'".format(config.workspace))
        sys.exit(-1)

    # get the function associated with the subcommand
    func = commands[command].load()

    if verbose:
        for log_handler in logging.getLogger().handlers[:]:
            if isinstance(log_handler, logging.StreamHandler):
                log_handler.setLevel(logging.DEBUG)

    # Call the function associated with the subcommand
    func(*args)


if __name__ == "__main__":
    main()
