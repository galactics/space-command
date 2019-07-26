import os
import sys
import asyncio
import aiohttp
import async_timeout
import requests
import logging
from datetime import datetime
from peewee import (
    Model,
    IntegerField,
    CharField,
    TextField,
    DateTimeField,
    SqliteDatabase,
    fn,
)

from beyond.io.tle import Tle

from .wspace import ws

log = logging.getLogger(__name__)


class TleNotFound(Exception):
    def __init__(self, selector, mode=None):
        self.selector = selector
        self.mode = mode

    def __str__(self):
        if self.mode:
            return "No TLE for {obj.mode} = '{obj.selector}'".format(obj=self)
        else:
            return "No TLE containing '{}'".format(self.selector)


class TleDb:

    SPACETRACK_URL_AUTH = "https://www.space-track.org/ajaxauth/login"
    # SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/>now-30/orderby/NORAD_CAT_ID/format/3le"
    # SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/orderby/NORAD_CAT_ID/format/3le/favorites/Amateur"

    SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/{mode}/{selector}/orderby/ORDINAL%20asc/limit/1/format/3le/emptyresult/show"

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
        "other.txt",
        "active.txt",
        "analyst.txt",
        "planet.txt",
        "spire.txt",
        "ses.txt",
        "iridium-NEXT.txt",
    ]

    db = SqliteDatabase(None)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):

        self._cache = {}
        self.model = TleModel
        self.db.init(str(ws.folder / "space.db"))
        self.model.create_table(safe=True)

    def dump(self, all=False):

        bd_request = self.model.select().order_by(self.model.norad_id)

        if not all:
            bd_request = bd_request.group_by(self.model.norad_id)

        for tle in bd_request:
            yield Tle("%s\n%s" % (tle.name, tle.data), src=tle.src)

    def fetch(self, src=None, **kwargs):

        if src == "spacetrack":
            self.fetch_spacetrack(**kwargs)
        elif src == "celestrak":
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.fetch_celestrak(**kwargs))
        else:
            raise ValueError("Unknown source '{}'".format(src))

    def fetch_spacetrack(self, **kwargs):

        try:
            auth = ws.config["spacetrack"]
        except KeyError:
            raise ValueError("No login information available for spacetrack")

        _conv = {
            "norad_id": "NORAD_CAT_ID",
            "cospar_id": "INTLDES",
            "name": "OBJECT_NAME",
        }

        key = next(iter(kwargs.keys()))
        url = self.SPACETRACK_URL.format(mode=_conv[key], selector=kwargs[key])

        log.debug("Authentication to Space-Track website")
        init = requests.post(self.SPACETRACK_URL_AUTH, auth)

        try:
            init.raise_for_status()
        except requests.exceptions.HTTPError as e:
            log.error("Authentication failed")
            log.exception(e)
            raise

        if init.text != '""':
            log.error("Authentication failed")
            log.debug("Response from authentication page '{}'".format(init.text))
            return

        log.debug("Authorized to proceed")
        log.debug("Request at {}".format(url))
        full = requests.get(url, cookies=init.cookies)

        cache = ws.folder / "tmp" / "spacetrack.txt"
        log.debug("Caching results into {}".format(cache))
        with cache.open("w") as fp:
            fp.write(full.text)

        full.raise_for_status()

        self.insert(full.text, "spacetrack.txt")

    async def fetch_file(self, session, filename):
        """Coroutine to retrieve the specified page

        When the page is totally retrieved, the function will call insert
        """
        with async_timeout.timeout(30):
            async with session.get(self.CELESTRAK_URL + filename) as response:
                text = await response.text()

                filepath = ws.folder / "tmp" / "celestrak" / filename

                if not filepath.parent.exists():
                    filepath.parent.mkdir(parents=True)

                with filepath.open("w") as fp:
                    fp.write(text)

                self.insert(text, filename)

    async def fetch_celestrak(self, files=None):
        """Retrieve TLE from the celestrak.com website asynchronously
        """

        if files is None:
            filelist = self.CELESTRAK_PAGES
        else:
            # Filter out file not included in the base list
            files = set(files)
            filelist = files.intersection(self.CELESTRAK_PAGES)
            remaining = files.difference(self.CELESTRAK_PAGES)

            for p in remaining:
                log.warning("Unknown celestrak pages '{}'".format(p))

            if not filelist:
                raise ValueError("No file to download")

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
            return (
                self.model.select()
                .filter(**kwargs)
                .order_by(self.model.epoch.desc())
                .get()
            )
        except TleModel.DoesNotExist as e:
            mode, selector = kwargs.popitem()
            raise TleNotFound(selector, mode=mode) from e

    @classmethod
    def get_dated(cls, limit=None, date=None, **kwargs):

        self = cls()

        if limit == "after":
            r = (
                self.model.select()
                .where(self.model.epoch >= date)
                .order_by(self.model.epoch.asc())
            )
        else:
            r = self.model.select().where(self.model.epoch <= date)

        try:
            entity = r.filter(**kwargs).get()
        except self.model.DoesNotExist:
            mode, selector = kwargs.popitem()
            raise TleNotFound(selector, mode=mode) from e
        else:
            return Tle("%s\n%s" % (entity.name, entity.data), src=entity.src)

    def history(self, number=None, **kwargs):
        """Retrieve all the TLE of a given object

        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
        Yield:
            TleModel:
        """

        query = self.model.select().filter(**kwargs).order_by(self.model.epoch)

        if not query:
            mode, selector = kwargs.popitem()
            raise TleNotFound(selector, mode=mode)

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
            i = None
            for i, tle in enumerate(Tle.from_string(text)):
                try:
                    # An entry in the table correponding to this TLE has been
                    # found, there is no need to update it
                    entity = self.model.get(
                        self.model.norad_id == tle.norad_id,
                        self.model.epoch == tle.epoch.datetime,
                    )
                    continue
                except TleModel.DoesNotExist:
                    # This TLE is not registered yet, lets go !
                    entity = {
                        "norad_id": int(tle.norad_id),
                        "cospar_id": tle.cospar_id,
                        "name": tle.name,
                        "data": tle.text,
                        "epoch": tle.epoch.datetime,
                        "src": src,
                        "insert_date": datetime.now(),
                    }
                    entities.append(entity)

            if entities:
                TleModel.insert_many(entities).execute()
            elif i is None:
                raise ValueError("{} contains no TLE".format(src))

        log.info("{:<20}   {:>3}/{}".format(src, len(entities), i + 1))

    def find(self, txt):
        """Retrieve every TLE containing a string. For each object, only get the
        last TLE in database

        Args:
            txt (str)
        Return:
            Tle:
        """

        entities = (
            self.model.select()
            .where(self.model.data.contains(txt) | self.model.name.contains(txt))
            .order_by(self.model.norad_id, self.model.epoch.desc())
            .group_by(self.model.norad_id)
        )

        sats = []
        for entity in entities:
            sats.append(Tle("%s\n%s" % (entity.name, entity.data), src=entity.src))
        if not sats:
            raise TleNotFound(txt)

        return sats


def print_stats():
    db = TleDb()
    first = db.model.select(fn.MIN(TleModel.insert_date)).scalar()
    last = db.model.select(fn.MAX(TleModel.insert_date)).scalar()

    print(
        "Objects       {}".format(db.model.select().group_by(TleModel.norad_id).count())
    )
    print("TLE           {}".format(db.model.select().count()))
    print("First fetch   {}".format(first))
    print("Last fetch    {}".format(last))


class TleModel(Model):

    norad_id = IntegerField()
    cospar_id = CharField()
    name = CharField()
    data = TextField()
    epoch = DateTimeField()
    src = TextField()
    insert_date = DateTimeField()

    class Meta:
        database = TleDb.db


TleModel.add_index(TleModel.norad_id.desc(), TleModel.epoch.desc(), unique=True)


def wshook(cmd, *args, **kwargs):

    if cmd == "full-init":
        try:
            TleDb.get(norad_id=25544)
        except TleNotFound:
            TleDb().fetch(src="celestrak")
            log.info("TLE database initialized")
        else:
            log.info("TLE database already exists")
    elif cmd == "status":
        print()
        print("TLE")
        print("---")
        print_stats()


def space_tle(*argv):
    """TLE Database from Space-Track and Celestrak websites

    Usage:
      space-tle get <selector>...
      space-tle insert (-|<file>...)
      space-tle fetch [<file>...]
      space-tle fetch-st <selector>...
      space-tle find <text> ...
      space-tle history [--last <nb>] <selector>...
      space-tle dump [--all]
      space-tle stats

    Options:
      dump             Display the last TLE for each object
      fetch            Retrieve TLEs from Celestrak website
      fetch-st         Retrieve a single TLE for a given object from the Space-Track
                       website. This request needs login informations (see below)
      find             Search for a string in the database of TLE (case insensitive)
      get              Display the last TLE of a selected object
      history          Display all the recorded TLEs for a given object
      insert           Insert TLEs into the database (file or stdin)
      stats            Display statistics on the database
      <selector>       Selector of the object, see `space sat`
      <file>           File to insert in the database
      -l, --last <nb>  Get the last <nb> TLE
      -a, --all        Display the entirety of the database, instead of only
                       the last TLE of each object

    Examples:
      space tle fetch                # Retrieve all the TLEs from celestrak
      space tle fetch visual.txt     # Retrieve only that file from celestrak
      space tle norad=25544          # Display the TLE of the ISS
      space tle cospar=1998-067A     # Display the TLE of the ISS, too
      space tle insert file.txt      # Insert all TLEs from the file
      echo "..." | space tle insert  # Insert TLEs from stdin

    Configuration:
      The Space-Track website only allows TLE downloads from logged-in requests.
      To do this, the config file should contain
          spacetrack:
              identity: <login>
              password: <password>
      
      Every time you retrieve or insert TLE in the database, the satellite database
      is updated. To disable this behaviour add the following to the config file
          satellites:
              auto-sync-tle: False
    """

    from .utils import docopt
    from .sat import Sat, Request, sync

    from glob import glob

    args = docopt(space_tle.__doc__, argv=argv)

    db = TleDb()

    if args["fetch"] or args["fetch-st"]:
        kwargs = {}
        src = "celestrak" if args["fetch"] else "spacetrack"

        if src == "celestrak" and args["<file>"]:
            kwargs["files"] = args["<file>"]
        elif src == "spacetrack":
            try:
                sat = Sat.from_input(*args["<selector>"])
            except ValueError:
                desc = Request.from_text(*args["<selector>"])
                kwargs[desc.selector] = desc.value
            else:
                kwargs["norad_id"] = sat.norad_id

        kwargs["src"] = src

        log.info("Retrieving TLEs from {}".format(src))

        try:
            db.fetch(**kwargs)
        except ValueError as e:
            log.error(e)
        finally:
            if ws.config.get("satellites", "auto-sync-tle", fallback=True):
                # Update the Satellite DB
                sync("tle")

    elif args["insert"]:
        # Process the file list provided by the command line
        if args["<file>"]:
            files = []
            for f in args["<file>"]:
                files.extend(glob(f))

            # Insert each file into the database
            for file in files:
                try:
                    db.load(file)
                except Exception as e:
                    log.error(e)

        elif args["-"] and not sys.stdin.isatty():
            try:
                # Insert the content of stdin into the database
                db.insert(sys.stdin.read(), "stdin")
            except Exception as e:
                log.error(e)
        else:
            log.error("No TLE provided")
            sys.exit(1)

        if ws.config.get("satellites", "auto-sync-tle", fallback=True):
            # Update the Satellite DB
            sync()

    elif args["find"]:
        txt = " ".join(args["<text>"])
        try:
            result = db.find(txt)
        except TleNotFound as e:
            log.error(str(e))
            sys.exit(1)

        for tle in result:
            print("{0.name}\n{0}\n".format(tle))

        log.info("==> {} entries found for '{}'".format(len(result), txt))
    elif args["dump"]:
        for tle in db.dump(all=args["--all"]):
            print("{0.name}\n{0}\n".format(tle))
    elif args["stats"]:
        print_stats()
    else:
        try:
            sats = list(Sat.from_selector(*args["<selector>"]))
        except ValueError as e:
            log.error(str(e))
            sys.exit(1)

        for sat in sats:
            try:
                if args["history"]:
                    number = int(args["--last"]) if args["--last"] is not None else None
                    tles = db.history(number=number, cospar_id=sat.cospar_id)

                    for tle in tles:
                        print("{0.name}\n{0}\n".format(tle))
                else:
                    tle = db.get(cospar_id=sat.cospar_id)
                    print("{0.name}\n{0}\n".format(tle))
            except TleNotFound as e:
                log.error(str(e))
                sys.exit(1)
