import sys
import yaml
import logging.config
from pathlib import Path
from textwrap import indent
from datetime import datetime, timedelta

from beyond.config import config as beyond_config, Config as LegacyConfig


class SpaceConfig(LegacyConfig):

    filepath = Path.home() / '.space/space.yml'

    def __new__(cls, *args, **kwargs):

        if isinstance(cls._instance, LegacyConfig):
            cls._instance = None

        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)

        return cls._instance

    def set(self, *args, save=True):
        super().set(*args)
        self.save()

    @property
    def folder(self):
        return self.filepath.parent

    def init(self, folder=None):

        if folder:
            self.filepath = Path(folder) / self.filepath.name

        if self.filepath.exists():
            raise FileExistsError(self.filepath)

        if not self.folder.exists():
            self.folder.mkdir()

        self.update({
            'beyond': {
                'eop': {
                    'missing_policy': "pass",
                }
            },
            'aliases': {
                'ISS': 25544
            },
            'stations': {
                'TLS': {
                    'latlonalt': (43.604482, 1.443962, 172.0),
                    'name': 'Toulouse',
                    'orientation': 'N',
                    'parent_frame': 'WGS84'
                }
            }
        })
        self.save()

    def load(self, filepath=None):
        """Load the config file and create missing directories
        """

        if filepath:
            self.filepath = Path(filepath)

        data = yaml.load(self.filepath.open())
        self.update(data)

        beyond_config.update(self['beyond'])

        if 'logging' in self.keys():
            logging.config.dictConfig(self['logging'])
        else:
            logging.basicConfig(level="INFO", format="%(message)s")

    def save(self):
        yaml.dump(dict(self), self.filepath.open('w'), indent=4)


config = SpaceConfig()


def load_config(path=None, walkback=True):

    if not path and walkback:
        # Search a config.yml file in the current folder and its parents
        cwd = Path.cwd()
        for folder in [cwd] + list(cwd.parents):

            fpath = folder.joinpath(SpaceConfig.filepath.name)

            if fpath.exists():
                path = fpath
                break

    try:
        config.load(path)
    except FileNotFoundError as e:
        print("The config file '%s' does not exist." % e.filename)
        print("Please create it with the 'space config init' command")
        sys.exit(-1)


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

    def __init__(self, path):
        self.path = path

    @property
    def duration(self):
        return timedelta(minutes=5)

    def unlock(self):
        with self.path.open('w') as fp:
            fp.write(datetime.now().strftime(self.fmt))

    def lock(self):
        if not self.locked(verbose=False):
            self.path.unlink()

    def locked(self, verbose=True):
        if self.path.exists():
            txt = self.path.open().read().strip()
            date = datetime.strptime(txt, self.fmt)
            td = datetime.now() - date
            if td < self.duration:
                return False

        if verbose:
            print("Config file locked. Please use 'space config unlock' first")
        return True


def space_config(*argv):
    """Configuration handling

    Usage:
      space-config edit
      space-config set <keys> <value>
      space-config init [<folder>]
      space-config unlock
      space-config lock
      space-config [get] [<keys>]

    Options:
      unlock    Enable command-line config alterations for the next 5 minutes
      lock      Disable command-line config alterations
      get       Print the value of the selected fields
      set       Set the value of the selected field (needs unlock)
      edit      Open the text editor defined via $EDITOR env variable (needs unlock)
      init      Create config file and directory
      <keys>    Field selector, in the form of key1.key2.key3...
      <value>   Value to set the field to
      <folder>  Folder in which to create the config file

    Examples:
      space config set aliases.ISS 25544
      space config aliases.ISS

    """

    import os
    import shutil
    from subprocess import run

    from .utils import docopt

    args = docopt(space_config.__doc__)

    if args['init']:
        try:
            config.init(args['<folder>'])
        except FileExistsError:
            print("Config file already existing at '%s'" % config.filepath, file=sys.stderr)
        else:
            print("config creation at", config.filepath, file=sys.stderr)
    else:
        load_config()

        lock = Lock(config.filepath.with_name(".config_unlock"))

        if args['edit']:
            if not lock.locked():
                run([os.environ['EDITOR'], str(config.filepath)])
        elif args['set']:
            if not lock.locked():
                try:
                    config.set(*args['<keys>'].split('.'), args['<value>'], save=False)
                except TypeError as e:
                    # For some reason we don't have the right to set this
                    # value
                    print(e, file=sys.stderr)
                    sys.exit(-1)
                else:
                    # If everything went fine, we save the file in its new state
                    config.save()

        elif args['unlock']:
            print("Are you sure you want to unlock the config file ?")
            ans = input(" yes/[no] ")

            if ans.lower() == "yes":
                lock.unlock()

                backup = config.filepath.with_suffix(config.filepath.suffix + '.backup')
                shutil.copy2(config.filepath, backup)

                print()
                print("A backup of the current config file has been created at")
                print(backup)
                print()
        elif args["lock"]:
            lock.lock()
        else:

            subdict = config

            try:
                if args['<keys>']:
                    for k in args['<keys>'].split("."):
                        subdict = subdict[k]
            except KeyError as e:
                print("Unknown field", e, file=sys.stderr)
                sys.exit(-1)

            if hasattr(subdict, 'filepath'):
                print("config :", config.filepath)
            if isinstance(subdict, dict):
                # print a part of the dict
                print(get_dict(subdict))
            else:
                # Print a single value
                print(subdict)
