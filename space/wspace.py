import os
import sys
import shutil
import logging
import subprocess
from pathlib import Path
from pkg_resources import iter_entry_points

from .utils import docopt
from .config import config

log = logging.getLogger(__name__)


def trigger_hooks(cmd):
    if cmd == "status":
        print("Workspace '{}'".format(config.workspace))
    elif cmd == "init":
        print("Initializing workspace '{}'".format(config.workspace))
    # elif cmd == "full-init":
    #     log.info("Full initialization of workspace '{}'".format(config.workspace))
    else:
        log.error("Unknown command '{}'".format(cmd))
        # sys.exit(-1)
        raise

    # Each command is responsible of its own initialization, logging and error handling
    for entry in sorted(iter_entry_points('space.wshook'), key=lambda x:x.name):
        entry.load()(cmd)


def wspace(*argv):
    """Workspace management for the space command

    Usage:
        wspace list
        wspace (status|init) [<name>]
        wspace delete <name>

    Options:
        init       Initialize workspace
        list       List existing workspaces
        delete     Delete a workspace
        <name>     Name of the workspace to work in

    Examples
    
        $ export SPACE_WORKSPACE=test  # switch workspace
        $ wspace init                  # Create empty data structures
        $ space tle fetch              # Retrieve TLEs from celestrak

    is equivalent to:

        $ wspace init test
        $ space tle fetch -w test

    """

    args = docopt(wspace.__doc__, argv=sys.argv[1:])

    if args['delete']:
        # Deletion of a workspace
        ws = config.WORKSPACES.joinpath(args["<name>"])
        if not ws.exists():
            print("The workspace '{}' does not exist".format(args['<name>']))
        else:
            print("If you are sure to delete the workspace '{}', please enter it's name".format(args['<name>']))

            answer = input("> ")
            if answer == args['<name>']:
                shutil.rmtree(str(ws))
                print("{} deleted".format(ws))
            else:
                print("Deletion canceled")
    else:
        # The following commands need the `config.workspace` variable set
        # in order to work properly

        if args['<name>']:
            config.workspace = args['<name>']
        elif 'SPACE_WORKSPACE' in os.environ:
            config.workspace = os.environ['SPACE_WORKSPACE']

        if args['list']:
            for ws in config.WORKSPACES.iterdir():
                if ws.is_dir():
                    if config.workspace == ws.name:
                        mark = "*"
                        color = "\033[32m"
                        endc = "\033[39m"
                    else:
                        mark = ""
                        color = ""
                        endc = ""
                    print("{:1} {}{}{}".format(mark, color, ws.name, endc))
            sys.exit(0)
        else:
            # Pass the subcommand to the proper module
            cmd = [k for k, v in args.items() if v and not k.startswith('<')][0]
            trigger_hooks(cmd)
