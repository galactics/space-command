import sys
import yaml
import shutil
import logging.config
from pathlib import Path
from textwrap import indent
from datetime import datetime, timedelta

from beyond.config import config as beyond_config, Config as BeyondConfig

log = logging.getLogger(__name__)


class SpaceFilter(logging.Filter):
    """Specific logging filter in order to keep messages from space commands
    and the beyond library
    """

    def filter(self, record):
        pkg, sep, rest = record.name.partition(".")
        return pkg in ("space", "beyond")


class SpaceConfig(BeyondConfig):

    verbose = False

    def __init__(self, workspace):
        self.workspace = workspace

    @property
    def filepath(self):
        return self.workspace.folder / "config.yml"

    def set(self, *args, save=False):
        super().set(*args)
        if save:
            self.save()

    def init(self):
        """Initialize a given workspace folder and config file
        """

        if self.filepath.exists():
            raise FileExistsError(self.filepath)

        self.update({"beyond": {"eop": {"missing_policy": "pass"}}})
        self.save()

    def load(self):
        """Load the config file and create missing directories
        """

        data = yaml.safe_load(self.filepath.open())
        self.update(data)

        beyond_config.update(self["beyond"])

        if "logging" in self.keys():
            logging_dict = self["logging"]
        else:
            logging_dict = {
                "disable_existing_loggers": False,
                "filters": {"space_filter": {"()": SpaceFilter}},
                "formatters": {
                    "dated": {
                        "format": "%(asctime)s.%(msecs)03d :: %(name)s :: %(levelname)s :: %(message)s",
                        "datefmt": "%Y-%m-%dT%H:%M:%S",
                    },
                    "simple": {"format": "%(message)s"},
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "formatter": "simple",
                        "level": "INFO" if not self.verbose else "DEBUG",
                        "filters": ["space_filter"],
                    },
                    "debug_file_handler": {
                        "backupCount": 5,
                        "when": "W2",
                        "class": "logging.handlers.TimedRotatingFileHandler",
                        "encoding": "utf8",
                        "filename": str(self.filepath.parent / "space.log"),
                        "filters": ["space_filter"],
                        "formatter": "dated",
                        "level": "DEBUG",
                    },
                },
                "loggers": {
                    "space_logger": {
                        "handlers": ["console", "debug_file_handler"],
                        "level": "DEBUG",
                        "propagate": False,
                    }
                },
                "root": {
                    "handlers": ["console", "debug_file_handler"],
                    "level": "DEBUG",
                },
                "version": 1,
            }

        logging.config.dictConfig(logging_dict)

    def save(self):
        yaml.safe_dump(dict(self), self.filepath.open("w"), indent=4)


def get_dict(d):
    txt = []
    for k, v in d.items():
        if isinstance(v, dict):
            txt.append("%s:\n%s" % (k, indent(get_dict(v), " " * 4)))
        elif isinstance(v, (list, tuple)):
            txt.append("%s:\n%s" % (k, indent("\n".join([str(x) for x in v]), " " * 4)))
        else:
            txt.append("%s: %s" % (k, v))
    return "\n".join(txt)


class Lock:

    fmt = "%Y-%m-%dT%H:%M:%S"
    duration = timedelta(minutes=5)

    def __init__(self, file):
        self.file = Path(file)

    @property
    def lock_file(self):
        return self.file.with_name(".unlock_" + self.file.stem)

    @property
    def backup(self):
        return self.file.with_suffix(self.file.suffix + ".backup")

    def unlock(self):

        until = datetime.now() + self.duration

        with self.lock_file.open("w") as fp:
            fp.write(until.strftime(self.fmt))

        shutil.copy2(str(self.file), str(self.backup))

        log.info("Unlocking {} until {:{}}".format(self.file, until, self.fmt))
        log.debug(
            "A backup of the current config file has been created at {}".format(
                self.backup
            )
        )

    def lock(self):
        if self.lock_file.exists():
            self.lock_file.unlink()
            log.info("Locking the config file")
        else:
            log.info("The config file is already locked")

    def locked(self):
        if self.lock_file.exists():
            txt = self.lock_file.open().read().strip()
            until = datetime.strptime(txt, self.fmt)
            return until < datetime.now()

        return True


def wshook(cmd):

    from .wspace import ws

    if cmd in ("init", "full-init"):

        try:
            ws.config.init()
        except FileExistsError as e:
            ws.config.load()
            log.warning(
                "config file already exists at '{}'".format(Path(str(e)).absolute())
            )
        else:
            ws.config.load()  # Load the newly created config file
            log.info("config creation at {}".format(ws.config.filepath.absolute()))


def space_config(*argv):
    """Configuration handling

    Usage:
      space-config edit
      space-config set [--append] <keys> <value>
      space-config unlock [--yes]
      space-config lock
      space-config [get] [<keys>]

    Options:
      unlock    Enable command-line config alterations for the next 5 minutes
      lock      Disable command-line config alterations
      get       Print the value of the selected fields
      set       Set the value of the selected field (needs unlock)
      edit      Open the text editor defined via $EDITOR env variable (needs unlock)
      <keys>    Field selector, in the form of key1.key2.key3...
      <value>   Value to set the field to
      <folder>  Folder in which to create the config file
      --append  Append the value to a list

    Examples:
      space config set aliases.ISS 25544
      space config aliases.ISS

    """

    import os
    from subprocess import run

    from .utils import docopt
    from space.wspace import ws

    args = docopt(space_config.__doc__)

    lock = Lock(ws.config.filepath)

    if args["edit"]:
        if not lock.locked():
            run([os.environ["EDITOR"], str(ws.config.filepath)])
            if lock.file.read_text() == lock.backup.read_text():
                log.info("Unchanged config file")
            else:
                log.info("Config file modified")
        else:
            print(
                "Config file locked. Please use 'space config unlock' first",
                file=sys.stderr,
            )
            sys.exit(1)
    elif args["set"]:
        if not lock.locked():
            try:
                keys = args["<keys>"].split(".")
                if args["--append"]:
                    prev = ws.config.get(*keys, fallback=[])
                    if not isinstance(prev, list):
                        if isinstance(prev, str):
                            prev = [prev]
                        else:
                            prev = list(prev)
                    prev.append(args["<value>"])
                    ws.config.set(*keys, prev, save=False)
                else:
                    ws.config.set(*keys, args["<value>"], save=False)
            except TypeError as e:
                # For some reason we don't have the right to set this
                # value
                print(e, file=sys.stderr)
                sys.exit(1)
            else:
                # If everything went fine, we save the file in its new state
                ws.config.save()
                log.debug(
                    "'{}' now set to '{}'".format(args["<keys>"], args["<value>"])
                )
        else:
            print(
                "Config file locked. Please use 'space config unlock' first",
                file=sys.stderr,
            )
            sys.exit(1)

    elif args["unlock"]:
        if args["--yes"]:
            lock.unlock()
        else:
            print("Are you sure you want to unlock the config file ?")
            ans = input(" yes/[no] ")

            if ans.lower() == "yes":
                lock.unlock()
            elif ans.lower() != "no":
                print("unknown answer '{}'".format(ans), file=sys.stderr)
                sys.exit(1)
    elif args["lock"]:
        lock.lock()
    else:

        subdict = ws.config

        try:
            if args["<keys>"]:
                for k in args["<keys>"].split("."):
                    subdict = subdict[k]
        except KeyError as e:
            print("Unknown field", e, file=sys.stderr)
            sys.exit(1)

        if hasattr(subdict, "filepath"):
            print("config :", ws.config.filepath)
        if isinstance(subdict, dict):
            # print a part of the dict
            print(get_dict(subdict))
        else:
            # Print a single value
            print(subdict)


def space_log(*argv):
    """Display the log

    Usage:
      space-log [options]

    Options:
      -p, --print        Print instead of shoing the log via less
      -n, --lines <num>  When printing define the number of lines to print [default: 20]
      -v, --verbose      Print DEBUG messages as well
      -f, --follow       Start directly in tail mode
    """
    import subprocess

    from space.utils import docopt
    from space.wspace import ws

    logfile = ws.folder / "space.log"

    args = docopt(space_log.__doc__, argv=argv)

    if args["--print"]:
        nb = int(args["--lines"])

        lines = logfile.read_text().splitlines()
        filtered_lines = [
            l for l in lines if ws.config.verbose or ":: DEBUG ::" not in l
        ]

        for line in filtered_lines[-nb:]:
            print(line)
    else:
        try:
            # Handling the arguments of less
            # +G is for going directly at the bottom of the file
            # +F is for tail mode
            # -K is for "quit on iterrupt"
            # -S chops long lines
            opt = "+F" if args["--follow"] else "+G"
            f = subprocess.call(["less", "-KS", opt, str(logfile)])
        except KeyboardInterrupt:
            pass
