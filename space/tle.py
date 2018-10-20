import os
import sys
import asyncio
import aiohttp
import async_timeout
import requests
import logging
from peewee import (
    Model, IntegerField, CharField, TextField, DateField, SqliteDatabase
)
from datetime import datetime

from beyond.orbits.tle import Tle

from .config import config
from .satellites import Satellite


log = logging.getLogger(__name__)


class TleNotFound(Exception):

    def __init__(self, mode, selector):
        self.mode = mode
        self.selector = selector

    def __str__(self):
        return "Unknown TLE for {obj.mode} = '{obj.selector}'".format(obj=self)


class TleDb:

    SPACETRACK_URL_AUTH = "https://www.space-track.org/ajaxauth/login"
    # SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/>now-30/orderby/NORAD_CAT_ID/format/3le"
    # SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/orderby/NORAD_CAT_ID/format/3le/favorites/Amateur"

    SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/{mode}/{selector}/orderby/ORDINAL%20asc/limit/1/format/3le/emptyresult/show"

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
        self.db.init(str(config.folder / "space.db"))
        self.model.create_table(fail_silently=True)

    def purge(self):
        if not self.dbpath.exists():
            # Création de la table
            self.db.create_table(self.model)
        else:
            # Vidage de la table
            self.model.delete().execute()

    def fetch(self, src=None, **kwargs):

        if src == 'spacetrack':
            self.fetch_spacetrack(**kwargs)
        elif src == 'celestrak':
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.fetch_celestrak(**kwargs))
        else:
            raise ValueError("Unknown source '{}'".format(src))

    def fetch_spacetrack(self, **kwargs):

        try:
            auth = config['spacetrack']
        except KeyError:
            raise ValueError("No login information available for spacetrack")

        _conv = {
            'norad_id' : "NORAD_CAT_ID",
            'cospar_id': "INTLDES",
            'name': "OBJECT_NAME"
        }

        key = next(iter(kwargs.keys()))
        url = self.SPACETRACK_URL.format(
            mode=_conv[key],
            selector=kwargs[key]
        )

        init = requests.post(self.SPACETRACK_URL_AUTH, auth)
        full = requests.get(url, cookies=init.cookies)

        with open(config.folder / "tmp" / "spacetrack.txt", "w") as fp:
            fp.write(full.text)

        full.raise_for_status()

        self.insert(full.text, "spacetrack")

    async def fetch_file(self, session, filename):
        """Coroutine to retrieve the specified page

        When the page is totally retrieved, the function will call insert
        """
        with async_timeout.timeout(30):
            async with session.get(self.CELESTRAK_URL + filename) as response:
                text = await response.text()

                filepath = config.folder / "tmp" / "celestrak" / filename

                if not filepath.parent.exists():
                    filepath.parent.mkdir(parents=True)

                with filepath.open("w") as fp:
                    fp.write(text)

                self.insert(text, filename)

    async def fetch_celestrak(self, file=None):
        """Retrieve TLE from the celestrak.com website asynchronously
        """

        # filter the files which will be downloaded in order to minimize
        # the number of requests
        if file is not None:
            if file not in self.CELESTRAK_PAGES:
                raise ValueError("Unknown celestrak page '%s'" % file)

            filelist = [file]
        else:
            filelist = self.CELESTRAK_PAGES

        async with aiohttp.ClientSession() as session:

            # Task list initialisation
            tasks = [self.fetch_file(session, f) for f in filelist]

            await asyncio.gather(*tasks)

    @classmethod
    def get(cls, **kwargs):
        """Retrieve one TLE from the table from one of the available fields

        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
        Return:
            Satellite:
        """
        entity = cls()._get_last_raw(**kwargs)
        tle = Tle("%s\n%s" % (entity.name, entity.data), src=entity.src)
        sat = Satellite(
            name=tle.name,
            cospar_id=tle.cospar_id,
            norad_id=tle.norad_id,
            orb=tle.orbit(),
            tle=tle
        )
        return sat

    def _transform_kwargs(self, **kwargs):

        if 'name' in kwargs and kwargs['name'] in config['aliases']:
            kwargs = {"norad_id": config['aliases'][kwargs['name']]}

        return kwargs

    def _get_last_raw(self, **kwargs):
        """
        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
        Return:
            TleModel:
        """

        kwargs = self._transform_kwargs(**kwargs)

        try:
            return self.model.select().filter(**kwargs).order_by(self.model.epoch.desc()).get()
        except TleModel.DoesNotExist as e:
            mode, selector = kwargs.popitem()
            raise TleNotFound(mode, selector) from e

    def history(self, number=None, **kwargs):
        """Retrieve all the TLE of a given object

        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
        Yield:
            TleModel:
        """

        kwargs = self._transform_kwargs(**kwargs)

        try:
            query = self.model.select().filter(**kwargs).order_by(self.model.epoch)
        except TleModel.DoesNotExist as e:
            mode, selector = kwargs.popitem()
            raise TleNotFound(mode, selector) from e

        number = 0 if number is None else number

        for el in query[-number:]:
            yield Tle("%s\n%s" % (el.name, el.data), src=el.src)

    def load(self, filepath):
        """Insert the TLEs contained in a file in the database
        """
        with open(filepath) as fh:
            self.insert(fh.read(), os.path.basename(filepath))

    def insert(self, text, src):
        """
        Args:
            text (str): text containing the TLEs
            src (str): Where those TLEs come from
        Return:
            2-tuple: Number of tle inserted, total tle found in the text
        """

        with self.db.atomic():
            entities = []
            for i, tle in enumerate(Tle.from_string(text)):
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

        log.info("{:<20}   {:>3}/{}".format(src, len(entities), i + 1))

    def find(self, txt):
        """Retrieve every TLE containing a string. For each object, only get the
        last TLE in database

        Args:
            txt (str)
        Return:
            Satellite:
        """

        try:
            entities = (
                self.model.select()
                .where(self.model.data.contains(txt) | self.model.name.contains(txt))
                .order_by(self.model.epoch.desc())
                .group_by(self.model.norad_id)
                .order_by(self.model.norad_id)
            )
        except TleModel.DoesNotExist as e:
            raise TleNotFound("*", txt) from e

        sats = []
        for entity in entities:
            tle = Tle("%s\n%s" % (entity.name, entity.data), src=entity.src)
            sats.append(Satellite(
                name=tle.name,
                cospar_id=tle.cospar_id,
                norad_id=tle.norad_id,
                orb=tle.orbit(),
                tle=tle
            ))

        return sats


class TleModel(Model):

    norad_id = IntegerField()
    cospar_id = CharField()
    name = CharField()
    data = TextField()
    epoch = DateField()
    src = TextField()
    insert_date = DateField()

    class Meta:
        database = TleDb.db


TleModel.add_index(
    TleModel.norad_id.desc(),
    TleModel.epoch.desc(),
    unique=True
)


def space_tle(*argv):
    """Caching of TLE date from Space-Track and Celestrak websites

    Usage:
      space-tle insert [<file>]
      space-tle fetch [<file>]
      space-tle fetch-st <mode> <selector>
      space-tle find <text> ...
      space-tle history [--last <nb>] <mode> <selector> ...
      space-tle <mode> <selector> ...

    Options:
      fetch          Retrieve TLEs from Celestrak website
      fetch-st       Retrieve a TLE for a given object from the Space-Track website
                     This request needs login informations
      find           Search for a string in the database of TLE (case insensitive)
      insert         Insert TLEs into the database (file or stdin)
      history        Display all the recorded TLEs for a given object
      <mode>         Display the last TLE of an object. <mode> is the criterion
                     on which the research will be done. Available modes are
                     'norad', 'cospar' and 'name' (case sensitive)
      <selector>     Depending on <mode>, this field should be the NORAD-ID,
                     COSPAR-ID, or name of the desired object.
      <file>         File to insert in the database
      -l, --last <nb>  Get the last <nb> TLE

    Examples:
      space tle fetch                # Retrieve all the TLEs from celestrak
      space tle fetch visual.txt     # Retrieve only that file from celestrak
      space tle norad 25544          # Display the TLE of the ISS
      space tle cospar 1998-067A     # Display the TLE of the ISS, too
      space tle insert file.txt      # Insert all TLEs from the file
      echo "..." | space tle insert  # Insert TLEs from stdin

    Configuration:
      The Space-Track website only allows TLE downloads from logged-in request.
      To do this, the config file should contain
          spacetrack:
              identity: <login>
              password: <password>

      It is also possible to define aliases in the config dict to simplify name
      lookup:
        $ space tle name "ISS (ZARYA)"
      becomes
        $ space tle name ISS
      if the config file contains
          aliases:
              ISS: 25544

    """

    from .utils import docopt

    from glob import glob

    args = docopt(space_tle.__doc__)

    db = TleDb()

    if args['fetch'] or args['fetch-st']:

        kwargs = {}
        src = "celestrak" if args['fetch'] else "spacetrack"

        if src == 'celestrak' and args['<file>']:
            kwargs['file'] = args['<file>']
        elif src == "spacetrack":
            modes = {'norad': 'norad_id', 'cospar': 'cospar_id', 'name': 'name'}
            kwargs = {modes[args['<mode>']]: " ".join(args['<selector>'])}

        kwargs['src'] = src

        log.info("Retrieving TLEs from {}".format(src))

        try:
            db.fetch(**kwargs)
        except Exception as e:
            print(e)
            sys.exit(-1)
    elif args['insert']:

        if args['<file>']:
            if "*" in args['<file>']:
                files = glob(args['<file>'])
            else:
                files = [args['<file>']]

            for file in files:
                db.load(file)

        elif not sys.stdin.isatty():
            db.insert(sys.stdin.read(), "stdin")

    elif args['find']:
        txt = " ".join(args['<text>'])
        try:
            result = db.find(txt)
        except TleNotFound as e:
            log.error(str(e))
            sys.exit(-1)

        for sat in result:
            print("%s\n%s\n" % (sat.name, sat.tle))

        log.info("==> {} entries found for '{}'".format(len(result), txt))
    else:

        # Simply show a TLE
        modes = {'norad': 'norad_id', 'cospar': 'cospar_id', 'name': 'name'}
        kwargs = {modes[args['<mode>']]: " ".join(args['<selector>'])}

        try:
            if args['history']:
                number = int(args['--last']) if args['--last'] is not None else None
                tles = db.history(number=number, **kwargs)

                for tle in tles:
                    print("%s\n%s\n" % (tle.name, tle))
            else:
                sat = db.get(**kwargs)
                print("%s\n%s" % (sat.name, sat.tle))
        except TleNotFound as e:
            log.error(str(e))
            sys.exit(-1)
