import os
import sys
import uuid
import shutil
import logging
import tarfile
import subprocess
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from pkg_resources import iter_entry_points
from peewee import SqliteDatabase

from .utils import docopt, humanize
from .config import SpaceConfig

log = logging.getLogger(__name__)


def pm_on_crash(type, value, tb):
    """Exception hook, in order to start pdb when an exception occurs
    """
    import pdb
    import traceback

    traceback.print_exception(type, value, tb)
    pdb.pm()


@contextmanager
def switch_workspace(name, init=False, delete=False):
    """Temporarily switch workspace, with a context manager

    Args:
        name (str): Name of the workspace to temporarily load
        init (bool): If ``True``, this will perform an init of the workspace
        delete (bool): At the end of the use of the workspace, delete it
    Yield:
        Workspace 
    """
    old_name = ws.name
    ws.name = name

    try:
        if init:
            ws.init()

        ws.load()
        yield ws

        if delete:
            ws.delete()
    finally:
        ws.name = old_name


class Workspace:
    """Workspace handling class
    """

    WORKSPACES = Path(
        os.environ.get("SPACE_WORKSPACES_FOLDER", Path.home() / ".space/")
    )
    HOOKS = ("init", "status", "full-init")
    DEFAULT = "main"
    BACKUP_FOLDER = WORKSPACES / "_backup"

    def __new__(cls, *args, **kwargs):
        # Singleton
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, name=None):
        self.db = SqliteDatabase(None)
        self.db.ws = self
        self.config = SpaceConfig(self)
        self.name = name if name is not None else self.DEFAULT

    def __repr__(self):
        return "<Workspace '{}'>".format(self.name)

    @classmethod
    def list(cls):
        """List available workspaces
        """
        for _ws in cls.WORKSPACES.iterdir():
            if _ws.is_dir():
                if _ws.name == "_backup":
                    continue
                yield _ws

    def _db_init(self):
        filepath = self.folder / "space.db"
        self.db.init(str(filepath))
        log.debug("{} database initialized".format(filepath.name))

    def load(self):
        """Load the workspace
        """
        self.config.load()
        log.debug("{} loaded".format(self.config.filepath.name))
        self._db_init()
        log.debug("workspace '{}' loaded".format(self.name))

    def delete(self):
        if not self.folder.exists():
            raise FileNotFoundError(self.folder)

        shutil.rmtree(str(self.folder))
        log.info("Workspace '{}' deleted".format(self.name))

    @property
    def folder(self):
        """Path to the folder of this workspace, as a pathlib.Path object
        """
        return self.WORKSPACES / self.name

    def exists(self):
        return self.folder.exists()

    def init(self, full=False):
        """Initilize the workspace
        """

        print("Initializing workspace '{}'".format(self.name))
        if not self.exists():
            self.folder.mkdir(parents=True)

        # Due to the way peewee works, we have to initialize the database
        # even before the creation of any file
        self._db_init()

        if full:
            self._trigger("full-init")
        else:
            self._trigger("init")

        log.debug("{} workspace initialized".format(self.name))

    def status(self):
        log.info("Workspace '{}'".format(self.name))
        log.info("folder {}".format(self.folder))
        log.info("db     {}".format(self.db.database))
        log.info("config {}".format(self.config.filepath.name))
        self._trigger("status")

    def _trigger(self, cmd):
        if cmd not in self.HOOKS:
            raise ValueError("Unknown workspace command '{}'".format(cmd))

        # Each command is responsible of its own initialization, logging and error handling
        for entry in sorted(iter_entry_points("space.wshook"), key=lambda x: x.name):
            entry.load()(cmd)

    @classmethod
    def get_unique_name(self):
        while True:
            path = self.WORKSPACES.joinpath(str(uuid.uuid4()).split("-")[0])
            if not path.exists():
                break

        return path

    def backup(self, filepath=None):
        """Backup the current workspace into a tar.gz file
        """

        if filepath is None:
            name = "{}-{:%Y%m%d_%H%M%S}.tar.gz".format(self.name, datetime.utcnow())
            filepath = self.BACKUP_FOLDER / name
            if not filepath.parent.exists():
                filepath.parent.mkdir(parents=True)

        def _filter(tarinfo):
            """Filtering function
            """
            if "tmp" in tarinfo.name or "jpl" in tarinfo.name:
                return None
            else:
                return tarinfo

        log.info("Creating backup for workspace '{}'".format(self.name))
        with tarfile.open(filepath, "w:gz") as tar:
            tar.add(self.folder, arcname=self.name, filter=_filter)

        log.info("Backup created at {}".format(filepath))

    def restore(self, name, rename=None):
        filepath = self.BACKUP_FOLDER / name

        directory = self.get_unique_name() if rename else self.WORKSPACES

        with tarfile.open(filepath, "r:gz") as tar:
            tar.extractall(directory)

        if rename:
            directory.joinpath(self.name).replace(self.WORKSPACES.joinpath(rename))
            directory.rmdir()

    def list_backups(self):
        for bkp in self.BACKUP_FOLDER.glob("{}-*.tar.gz".format(self.name)):
            yield bkp


ws = Workspace()


def wspace(*argv):
    """Workspace management for the space command

    Usage:
        wspace list
        wspace status [<name>]
        wspace init [--full] [<name>]
        wspace backup create [<name>]
        wspace backup restore [<name>] [<backup>] [--rename <rename>]
        wspace backup [<name>]
        wspace delete <name>
        wspace on <name> [--init]
        wspace tmp [--init]

    Options:
        init       Initialize workspace
        list       List existing workspaces
        delete     Delete a workspace
        status     Print informations on a workspace
        backup     List available backups for a workspace
          create   Make a new backup
          restore  Restore a backup (possibly in a new workspace)
        <name>     Name of the workspace to work in
        --full     When initializating the workspace, retrieve data to fill it
                   (download TLEs from celestrak)
        --rename <rename>

    Examples
        $ export SPACE_WORKSPACE=test  # switch workspace
        $ wspace init                  # Create empty data structures
        $ space tle fetch              # Retrieve TLEs from celestrak
    is equivalent to:
        $ wspace init test
        $ space tle fetch -w test
    """

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if "--pdb" in sys.argv:
        sys.argv.remove("--pdb")
        sys.excepthook = pm_on_crash

    args = docopt(wspace.__doc__, argv=sys.argv[1:])

    if args["on"] or args["tmp"]:
        if "SPACE_WORKSPACE" in os.environ:
            log.error("Nested workspace activation prohibited")
            sys.exit(-1)

        if args["on"]:
            ws.name = args["<name>"]
        else:
            # Temporary workspace
            ws.name = ws.get_unique_name()

        if args["--init"]:
            ws.init()
        elif ws.name not in [w.name for w in Workspace.list()]:
            log.warning("The workspace '{}' is not initialized.".format(ws.name))
            log.warning("Run 'wspace init' to start working")

        # Duplication of environment variables, to add the SPACE_WORKSPACE variable
        env = os.environ.copy()
        env["SPACE_WORKSPACE"] = ws.name
        shell = env["SHELL"]

        subprocess.run([shell], env=env)

        if args["tmp"]:
            if ws.exists():
                ws.delete()

    elif args["delete"]:
        # Deletion of a workspace
        ws.name = args["<name>"]
        if not ws.exists():
            log.error("The workspace '{}' does not exist".format(args["<name>"]))
        else:
            print(
                "If you are sure to delete the workspace '{}', please enter its name".format(
                    args["<name>"]
                )
            )

            answer = input("> ")
            if answer == args["<name>"]:
                ws.delete()
            else:
                print("Deletion canceled")
    else:
        # The following commands need the `config.workspace` variable set
        # in order to work properly

        if args["<name>"]:
            name = args["<name>"]
        elif "SPACE_WORKSPACE" in os.environ:
            name = os.environ["SPACE_WORKSPACE"]
        else:
            name = Workspace.DEFAULT

        if args["list"] and not args["backup"]:
            for _ws in Workspace.list():
                if name == _ws.name:
                    mark = "*"
                    color = "\033[32m"
                    endc = "\033[39m"
                else:
                    mark = ""
                    color = ""
                    endc = ""
                print("{:1} {}{}{}".format(mark, color, _ws.name, endc))
            sys.exit(0)
        else:
            ws.name = name

            if args["init"]:
                ws.init(args["--full"])
            elif args["backup"]:
                if args["create"]:
                    ws.backup()
                elif args["restore"]:
                    backups = sorted(ws.list_backups(), reverse=True)
                    # Restore the last backup available

                    if not backups:
                        log.error(
                            "No backup available for workspace {}".format(ws.name)
                        )
                        sys.exit(1)
                    elif args["<backup>"] is None:
                        args["<backup>"] = backups[0].name
                    elif args["<backup>"] not in [x.name for x in backups]:
                        log.error(
                            "{} is not a valid backup for workspace {}".format(
                                args["<backup>"], ws.name
                            )
                        )
                        sys.exit(1)

                    print(
                        "Are you sure you want to restore the workspace '{}' with the backup {}".format(
                            args["--rename"] if args["--rename"] else ws.name,
                            args["<backup>"],
                        )
                    )
                    answer = input("yes/NO > ")
                    if answer == "yes":
                        ws.restore(args["<backup>"], args["--rename"])
                    else:
                        print("Restoration canceled")
                        sys.exit(1)
                else:
                    for bkp in sorted(ws.list_backups()):
                        print(
                            " {}  {:%Y-%m-%d %H:%M}  {}".format(
                                bkp.name,
                                datetime.fromtimestamp(bkp.stat().st_mtime),
                                humanize(bkp.stat().st_size),
                            )
                        )
            else:
                ws.load()
                ws.status()
