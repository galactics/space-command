import sys
import yaml
from pathlib import Path
from textwrap import indent

from beyond.config import config as beyond_config, Config as LegacyConfig


class SpaceConfig(LegacyConfig):

    filepath = Path.home() / '.space/space.yml'

    def __new__(cls, *args, **kwargs):

        if isinstance(cls._instance, LegacyConfig):
            cls._instance = None

        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)

        return cls._instance

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


def set_dict(d, keys, value):

    subdict = d

    *keys, last = keys

    for k in keys:
        subdict = subdict[k]

    if last in subdict and isinstance(subdict[last], dict):
        raise TypeError("Impossible to modify the structure of the file")

    subdict[last] = value


def space_config(*argv):
    """Configuration handling

    Usage:
      space-config edit
      space-config set <keys> <value>
      space-config init [<folder>]
      space-config [get] [<keys>]

    Options:
      edit      Open the text editor defined via $EDITOR env variable
      get       Print the value of the selected fields
      set       Set the value of the selected field
      init      Create config file and directory
      <keys>    Field selector, in the form of key1.key2.key3...
      <value>   Value to set the field to
      <folder>  Folder in which to create the config file

    Examples:
      space config set aliases.ISS 25544
      space config aliases.ISS

    """

    import os
    from .utils import docopt
    from subprocess import run

    args = docopt(space_config.__doc__)

    if args['init']:
        try:
            config.init(args['<folder>'])
        except FileExistsError:
            print("Config file already existing at '%s'" % config.filepath)
        else:
            print("config creation at", config.filepath)
    else:
        load_config()

        if args['edit']:
            run([os.environ['EDITOR'], str(config.filepath)])
        elif args['set']:
            try:
                set_dict(config, args['<keys>'].split('.'), args['<value>'])
            except TypeError as e:
                # For some reason we don't have the right to set this
                # value
                print(e)
                sys.exit(-1)
            else:
                # If everything went fine, we save the file in its new state
                config.save()
        else:

            print("config :", config.filepath)

            subdict = config

            if args['<keys>']:
                for k in args['<keys>'].split("."):
                    subdict = subdict[k]

            if isinstance(subdict, dict):
                # print a part of the dict
                print(get_dict(subdict))
            else:
                # Print a single value
                print(subdict)
