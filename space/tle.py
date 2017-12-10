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


class TleNotFound(Exception):

    def __init__(self, mode, selector):
        self.mode = mode
        self.selector = selector

    def __str__(self):
        return f"Unknown TLE for {self.mode} = '{self.selector}'"


class TleDatabase:

    SPACETRACK_URL_AUTH = "https://www.space-track.org/ajaxauth/login"
    SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/>now-30/orderby/NORAD_CAT_ID/format/3le"
    # SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/orderby/NORAD_CAT_ID/format/3le/favorites/Amateur"

    CELESTRAK_URL = "http://celestrak.com/NORAD/elements/"
    CELESTRAK_PAGES = [
        "stations.txt", "tle-new.txt", "visual.txt", "weather.txt", "noaa.txt",
        "goes.txt", "resource.txt", "sarsat.txt", "dmc.txt", "tdrss.txt",
        "argos.txt", "geo.txt", "intelsat.txt", "gorizont.txt", "raduga.txt",
        "molniya.txt", "iridium.txt", "orbcomm.txt", "globalstar.txt",
        "amateur.txt", "x-comm.txt", "other-comm.txt", "gps-ops.txt",
        "glo-ops.txt", "galileo.txt", "beidou.txt", "sbas.txt", "nnss.txt",
        "musson.txt", "science.txt", "geodetic.txt", "engineering.txt",
        "education.txt", "military.txt", "radar.txt", "cubesat.txt",
        "other.txt"
    ]

    db = SqliteDatabase(None)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):

        self._cache = {}
        self.model = TleModel
        self.db.init(str(config['env']['folder'] / "space.db"))
        self.model.create_table(fail_silently=True)

    def purge(self):
        if not self.dbpath.exists():
            # Création de la table
            self.db.create_table(self.model)
        else:
            # Vidage de la table
            self.model.delete().execute()

    def fetch(self, src=None, sat_list=None, file=None):
        if src == 'spacetrack':
            self.fetch_spacetrack(sat_list)
        else:
            self.fetch_celestrak(sat_list, file)

    def fetch_spacetrack(self, sat_list=None):
        auth = config['spacetrack']
        init = requests.post(self.SPACETRACK_URL_AUTH, auth)
        full = requests.get(self.SPACETRACK_URL, cookies=init.cookies)

        with open(config['env']['folder'] / "tmp" / "spacetrack.txt", "w") as fp:
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

                filepath = config['env']['folder'] / "tmp" / "celestrak" / filename

                if not filepath.parent.exists():
                    filepath.parent.mkdir(parents=True)

                with filepath.open("w") as fp:
                    fp.write(text)

                i = self.insert(text, "celestrak", filename)
                print("{:<20} {:>3}".format(filename, i))

    def fetch_celestrak(self, sat_list=None, file=None):
        """Retrieve TLE from the celestrak.com website asynchronously
        """

        # if a list of satellites is provided, filter the files which will be
        # download in order to minimize the number of requests
        if sat_list is not None:
            filelist = [sat.celestrak_file for sat in sat_list]
            filelist = list(set(filelist).intersection(self.CELESTRAK_PAGES))
        elif file is not None:
            if file not in self.CELESTRAK_PAGES:
                raise ValueError("Unknown celestrak page '%s'" % file)

            filelist = [file]
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
        except TleModel.DoesNotExist as e:
            mode, selector = kwargs.popitem()
            raise TleNotFound(mode, selector) from e

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


class TleModel(Model):

    norad_id = IntegerField()
    cospar_id = CharField()
    name = CharField()
    data = TextField()
    epoch = DateField()
    src = TextField()
    insert_date = DateField()

    class Meta:
        database = TleDatabase.db


def space_tle(*argv):
    """\
    Caching of TLE date from Space-Track and Celestrak websites

    Usage:
      space-tle insert <file>
      space-tle get [--full|--file <file>]
      space-tle <mode> <selector> ...

    Options:
      <mode>         Display the last TLE of an object. <mode> is the criterion
                     on which the research will be done. Available modes are
                     'norad', 'cospar' and 'name'
      <selector>     Depending on <mode>, this field should be the NORAD-ID,
                     COSPAR-ID, or name of the desired object.
      get            Retrieve data from Celestrak website
      --full         Retrieve the entire database
      --file <file>  Only retrieve one file from Celestrak
      insert         Insert a file into the database
      <file>         File to insert in the database

    Examples:
      space tle get         # Retrieve only the TLE of the satellites in the DB
      space tle get --full  # Retrieve all the files of celestrak
      space tle get --file visual.txt  # Retrieve only that file from celestrak
      space tle norad 25544       # Display the TLE of the ISS
      space tle cospar 1998-067A  # Display the TLE of the ISS, too
      space tle insert file.txt  # Insert all the TLE found in the file to the DB
    """

    from .satellites import Satellite
    from docopt import docopt
    from textwrap import dedent

    from glob import glob

    args = docopt(dedent(space_tle.__doc__), argv=argv)
    site = TleDatabase()

    if args['get']:
        kwargs = dict(src="celestrak", sat_list=None)

        if not args["--full"]:
            if args['--file']:
                kwargs['file'] = args['--file']
            else:
                try:
                    kwargs['sat_list'] = list(Satellite.get_all())
                except Exception:
                    # In case of missing file
                    kwargs['sat_list'] = None

        site.fetch(**kwargs)
    elif args['insert']:
        if "*" in args['<file>']:
            files = glob(args['<file>'])
        else:
            files = [args['<file>']]

        for file in files:
            site.load(file)
    else:

        # Simply show a TLE
        modes = {'norad': 'norad_id', 'cospar': 'cospar_id', 'name': 'name'}
        kwargs = {modes[args['<mode>']]: " ".join(args['<selector>'])}

        if args['<mode>'] == "name":
            # Try to match the name of the TLE with the satellite DB
            # If it doesn't work out, fallback to the names in the TLE DB
            try:
                sat = Satellite.get(**kwargs)
                kwargs = {'cospar_id': sat.cospar_id}
            except ValueError:
                pass

        try:
            entity = site.get_last(**kwargs)
        except TleNotFound as e:
            print(str(e))
            sys.exit(-1)

        print("%s\n%s" % (entity.name, entity))
