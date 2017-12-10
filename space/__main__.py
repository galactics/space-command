#!/usr/bin/env python

"""Space Command, a command for space application
"""

import sys
from pathlib import Path
from collections import OrderedDict, namedtuple
from importlib import import_module
from textwrap import dedent

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

    Command = namedtuple('Command', ['func', 'doc'])

    path = Path(__file__).parent

    commands = OrderedDict()

    for file in path.iterdir():
        try:
            module = import_module(".%s" % file.stem, 'space')
            for cmd in [getattr(module, x) for x in dir(module) if x.startswith('space_')]:
                name = cmd.__name__[6:]
                doc = dedent(cmd.__doc__.splitlines()[0]) if cmd.__doc__ is not None else ""
                commands[name] = Command(cmd, doc)
        except ModuleNotFoundError as e:
            print("%s : \"%s\"" % (file.stem, e))

    return commands


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
            helper += " {:<10} {}\n".format(name, cmd.doc)

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
    func = commands[command].func

    # Call the function associated with the subcommand
    func(*args)


if __name__ == "__main__":
    main()
