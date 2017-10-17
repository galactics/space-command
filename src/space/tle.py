import sys
import asyncio
import aiohttp
import signal
import requests
from peewee import (
    Model, IntegerField, CharField, TextField, DateField, SqliteDatabase
)
from datetime import datetime

from beyond.orbits.tle import Tle
from beyond.config import config


class TleModel(Model):

    norad_id = IntegerField()
    cospar_id = CharField()
    name = CharField()
    data = TextField()
    epoch = DateField()
    src = TextField()
    insert_date = DateField()

    class Meta:
        pass


class TleDatabase:

    SPACETRACK_URL_AUTH = "https://www.space-track.org/ajaxauth/login"
    SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/>now-30/orderby/NORAD_CAT_ID/format/3le"
    # SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/orderby/NORAD_CAT_ID/format/3le/favorites/Amateur"

    CELESTRAK_URL = "http://celestrak.com/NORAD/elements/"
    CELESTRAK_PAGES = [
        "stations.txt",
        "tle-new.txt",
        "visual.txt",
        "weather.txt",
        "noaa.txt",
        "goes.txt",
        "resource.txt",
        "sarsat.txt",
        "dmc.txt",
        "tdrss.txt",
        "argos.txt",
        "geo.txt",
        "intelsat.txt",
        "gorizont.txt",
        "raduga.txt",
        "molniya.txt",
        "iridium.txt",
        "orbcomm.txt",
        "globalstar.txt",
        "amateur.txt",
        "x-comm.txt",
        "other-comm.txt",
        "gps-ops.txt",
        "glo-ops.txt",
        "galileo.txt",
        "beidou.txt",
        "sbas.txt",
        "nnss.txt",
        "musson.txt",
        "science.txt",
        "geodetic.txt",
        "engineering.txt",
        "education.txt",
        "military.txt",
        "radar.txt",
        "cubesat.txt",
        "other.txt"
    ]

    dbfilename = "tle.db"

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):

        self._cache = {}
        self.model = TleModel
        self.model._meta.database = self.db

        if not self.dbpath.exists():
            # Création de la table
            self.db.create_table(self.model)

    @property
    def db(self):
        if 'db' not in self._cache:
            self._cache['db'] = SqliteDatabase(str(self.dbpath))
        return self._cache['db']

    @property
    def dbpath(self):
        return config['folder'] / self.dbfilename

    def purge(self):
        if not self.dbpath.exists():
            # Création de la table
            self.db.create_table(self.model)
        else:
            # Vidage de la table
            self.model.delete().execute()

    def fetch(self, src=None, sat_list=None):
        if src == 'spacetrack':
            self.fetch_spacetrack(sat_list)
        else:
            self.fetch_celestrak(sat_list)

    def fetch_spacetrack(self, sat_list=None):
        auth = config['spacetrack']
        init = requests.post(self.SPACETRACK_URL_AUTH, auth)
        full = requests.get(self.SPACETRACK_URL, cookies=init.cookies)

        with open(config['folder'] / "tmp" / "spacetrack.txt", "w") as fp:
            fp.write(full.text)

        i = self.insert(full.text, "spacetrack")
        print("spacetrack", i)

    async def fetch_file(self, session, filename):
        """Coroutine to retrieve the specified page

        When the page is totally retrieved, the function will call insert
        """
        with aiohttp.Timeout(30):
            async with session.get(self.CELESTRAK_URL + filename) as response:
                text = await response.text()

                with open(config['folder'] / "tmp" / ("celestrak_%s" % filename), "w") as fp:
                    fp.write(text)

                i = self.insert(text, "celestrak", filename)
                print("{:<20} {:>3}".format(filename, i))

    def fetch_celestrak(self, sat_list=None):
        """Retrieve TLE from the celestrak.com website asynchronously
        """

        # if a list of satellites is provided, filter the files which will be
        # download in order to minimize the number of requests
        if sat_list is not None:
            filelist = []
            for sat in sat_list:
                filename = sat._raw_raw_tle().src.replace("celestrak, ", "")
                filelist.append(filename)

            filelist = list(set(filelist).intersection(self.CELESTRAK_PAGES))
        else:
            filelist = self.CELESTRAK_PAGES

        loop = asyncio.get_event_loop()

        with aiohttp.ClientSession(loop=loop) as session:

            def signal_handler(signal, frame):
                """Interruption handling
                """
                loop.stop()
                session.close()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            # Task list initialisation
            tasks = []
            for p in filelist:
                tasks.append(asyncio.ensure_future(self.fetch_file(session, p)))

            # Triggering of tasks (asyncio.wait())
            loop.run_until_complete(asyncio.wait(tasks))
            loop.stop()
            session.close()

    @classmethod
    def get_last(cls, **kwargs):
        """Retrieve one TLE from the table from one of the available fields

        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
        Return:
            Tle:
        """
        entity = cls()._get_last_raw(**kwargs)
        return Tle("%s\n%s" % (entity.name, entity.data), src=entity.src)

    def _get_last_raw(self, **kwargs):
        """
        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
        Return:
            TleModel:
        """

        try:
            return self.model.select().filter(**kwargs).order_by(self.model.epoch.desc()).get()
        except TleModel.DoesNotExist:
            raise KeyError(
                "unknow TLE for {0[0]} = '{0[1]}'".format(list(kwargs.items())[0])
            )

    def load(self, filepath):
        with open(filepath) as fh:
            i = self.insert(fh.read(), "user input", filepath)

        print(filepath, i)

    def insert(self, text, src, filename=""):

        if filename != "":
            src = "%s, %s" % (src, filename)

        with self.db.atomic():
            entities = []
            for tle in Tle.from_string(text):
                try:
                    # An entry in the table correponding to this TLE has been
                    # found, there is no need to update it
                    entity = self.model.get(
                        self.model.norad_id == tle.norad_id,
                        self.model.epoch == tle.epoch.datetime
                    )
                    continue
                except TleModel.DoesNotExist:
                    # This TLE is not registered yet, lets go !
                    entity = {
                        'norad_id': int(tle.norad_id),
                        'cospar_id': tle.cospar_id,
                        'name': tle.name,
                        'data': tle.text,
                        'epoch': tle.epoch.datetime,
                        'src': src,
                        'insert_date': datetime.now(),
                    }
                    entities.append(entity)

            if entities:
                TleModel.insert_many(entities).execute()

        return len(entities)


def space_tle(*argv):
    """\
    Caching of TLE date from Space-Track and Celestrak websites

    Usage:
      space-tle get [--src <src>] [--full]
      space-tle show <mode> <selector>
      space-tle insert <file>

    Options:
      get          Retrieve data from Celestrak or Spacetrack websites
      show         Display TLE format for a given object
      insert       Insert a file into the database
      <mode>       Define the criterion on which the research will be done
                   Available modes are 'norad', 'cospar', 'name'
      <selector>   Depending on <mode>, this field should be the NORAD-ID,
                   COSPAR-ID, or name of the desired object.
      <file>       File to insert in the database
      --src <src>  Selection of the source of data ('celestrak' or
                   'spacetrack') [default: celestrak]
      --full       Retrieve the entire database
    """

    from .satellites import Satellite
    from docopt import docopt
    from textwrap import dedent

    from glob import glob

    args = docopt(dedent(space_tle.__doc__), argv=argv)
    site = TleDatabase()

    if args["--full"]:
        sat_list = None  # None means all satellites of the database
    else:
        sat_list = list(Satellite.get_all())

    if args['get']:
        site.fetch(src=args['--src'], sat_list=sat_list)
    elif args['show']:
        modes = {'norad': 'norad_id', 'cospar': 'cospar_id', 'name': 'name'}
        kwargs = {modes[args['<mode>']]: args['<selector>']}
        entity = site._get_last_raw(**kwargs)
        print("%s\n%s" % (entity.name, entity.data))
    elif args['insert']:
        if "*" in args['<file>']:
            files = glob(args['<file>'])
        else:
            files = [args['<file>']]

        for file in files:
            site.load(file)
