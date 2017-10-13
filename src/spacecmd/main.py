#!/usr/bin/env python

"""Space Command, a command for space application
"""

import sys
from pathlib import Path
from collections import OrderedDict, namedtuple
from importlib import import_module
from textwrap import dedent

from beyond.config import config


def exception(type, value, tb):
    import pdb
    import traceback
    traceback.print_exception(type, value, tb)
    pdb.pm()


def init():
    """Create a basic environment
    """
    config_path = Path.home() / '.space'
    if not config_path.exists():
        print("creation of '%s'" % config_path)
        config_path.mkdir()

    conf_file = config_path / "beyond.conf"
    if not conf_file.exists():
        print("beyond.conf initialisation")

        (config_path / "tmp").mkdir()

        with conf_file.open('w') as f:
            f.write("[env]\neop_source = daily")

        config.load(config_path)
    else:
        config.load(config_path)


def get_commands():

    Command = namedtuple('Command', ['func', 'doc'])

    path = Path(__file__).parent

    commands = OrderedDict()

    for file in path.iterdir():
        try:
            module = import_module(".%s" % file.stem, 'spacecmd')
            for cmd in [getattr(module, x) for x in dir(module) if x.startswith('spacecmd_')]:
                name = cmd.__name__[9:]
                doc = dedent(cmd.__doc__.splitlines()[0]) if cmd.__doc__ is not None else ""
                commands[name] = Command(cmd, doc)
        except ModuleNotFoundError as e:
            print("%s : \"%s\"" % (file.stem, e))

    return commands


def main():
    commands = get_commands()
    init()

    if "--pdb" in sys.argv:
        sys.excepthook = exception
        sys.argv.remove('--pdb')

    if len(sys.argv) <= 1 or sys.argv[1] not in commands:

        helper = "Available sub-commands :\n"
        helper += "\n".join(["  {:<8} {}".format(k, v[1]) for k, v in sorted(commands.items())])

        print(__doc__)
        print(helper)
        sys.exit(-1)

    command = sys.argv[1]
    sys.argv.pop(0)
    func = commands[command][0]

    func(*sys.argv[1:])
