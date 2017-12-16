#!/usr/bin/env python

"""Space Command, a command for space application
"""

import sys
from collections import OrderedDict
from pkg_resources import iter_entry_points

from . import __version__
from space.config import config


def exception(type, value, tb):
    """Exception hook, in order to start pdb when an exception occurs
    """
    import pdb
    import traceback
    traceback.print_exception(type, value, tb)
    pdb.pm()


def get_commands():
    """Retrieve available commands
    """

    commands = OrderedDict()

    for entry in iter_entry_points('subspace'):
        commands[entry.name] = entry

    return commands


def get_doc(func):
    return func.__doc__.splitlines()[0] if func.__doc__ is not None else ""


def main():
    """Direct the user to the right subcommand
    """

    if "--pdb" in sys.argv:
        sys.excepthook = exception
        sys.argv.remove('--pdb')

    if "--version" in sys.argv:
        import beyond

        print("Space-Command  {}".format(__version__))
        print("Beyond         {}".format(beyond.__version__))
        sys.exit(0)

    # load configuration and create missing folders
    config.load()

    # List of available subcommands
    commands = get_commands()

    if len(sys.argv) <= 1 or sys.argv[1] not in commands:
        # No or wrong subcommand

        helper = "Available sub-commands :\n"
        for name, cmd in sorted(commands.items()):
            cmd = cmd.load()
            helper += " {:<10} {}\n".format(name, get_doc(cmd))

        print(__doc__)
        print(helper)

        print("Options :")
        print(" --pdb      Launch the python debugger when an exception is raised")
        print(" --version  Show the version of the space-command utility")
        print()
        sys.exit(-1)

    # retrieve the subcommand and its arguments
    _, command, *args = sys.argv
    # get the function associated with the subcommand
    func = commands[command].load()

    # Load environment
    commands['env'].load()

    # Call the function associated with the subcommand
    func(*args)


if __name__ == "__main__":
    main()
