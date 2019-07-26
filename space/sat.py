import re
import sys
import logging
from textwrap import indent
from peewee import (
    Model,
    IntegerField,
    CharField,
    SqliteDatabase,
    IntegrityError,
    TextField,
)

from beyond.orbits import Ephem, Orbit
import beyond.io.ccsds as ccsds
from beyond.io.tle import Tle
from beyond.propagators import get_propagator
from beyond.env.solarsystem import get_body

from .clock import Date, timedelta
from .utils import parse_date, parse_timedelta
from .wspace import ws
from .ephem import EphemDb

log = logging.getLogger(__name__)


class NoDataError(ValueError):
    def __init__(self, req):
        self.req = req

    def __str__(self):
        return "No data for {req}".format(req=self.req)


class Request:
    """Request desrciptor

    Contain all the necessary elements to perform a search on satellite and orbit
    (TLE, OEM) databases
    """

    def __init__(self, selector, value, src, offset, limit, date):
        self.selector = selector
        """Field of selection"""

        self.value = value
        """Value of the field"""

        self.src = src
        """Source of orbit ('oem' or 'tle')"""

        self.offset = offset
        """Offset from the last orbit"""

        self.limit = limit
        """If a date is provided, define if the search should be done 'before' or 'after'"""

        self.date = date
        """Date of the research"""

    def __str__(self):

        txt = "{o.selector}={o.value}"

        if self.src is not None:
            txt += "@{o.src}"
        if self.offset > 0:
            txt += "~{o.offset}"
        if isinstance(self.date, Date):
            txt += "{limit}{o.date:%FT%T}"

        return txt.format(o=self, limit="^" if self.limit == "after" else "?")

    @classmethod
    def from_text(cls, txt, alias=True, **kwargs):
        """Convert a strin 'cospar=1998-067A@tle~~' to a Request object

        Any kwargs matching Request object attributes will override the text value
        For example ``Request.from_text("ISS@tle", src='oem')`` will deliver a
        request object with ``req.src == 'oem'``.

        Unseparable pairs are selector/value and limit/date respectively
        """

        delimiters = r"[@~\^\?\$]"

        if "selector" in kwargs and "value" in kwargs:
            selector = kwargs["selector"]
            value = kwargs["value"]
        else:
            selector_str = re.split(delimiters, txt)[0]

            if "=" in selector_str:
                selector, value = selector_str.split("=")
            else:
                selector, value = "name", selector_str

        if alias and selector == "name":
            # Retrieve alias if it exists
            rq = Alias.select().where(Alias.name == value)
            if rq.exists():
                selector, value = rq.get().selector.split("=")

        if selector in ("norad", "cospar"):
            selector += "_id"

        if selector not in ("name", "cospar_id", "norad_id"):
            raise ValueError("Unknown selector '{}'".format(selector))

        if "offset" in kwargs:
            offset = kwargs["offset"]
        else:
            # Compute the offset
            offset = 0
            if "~" in txt:
                offset = txt.count("~")
                if offset == 1:
                    m = re.search(r"~(\d+)", txt)
                    if m:
                        offset = int(m.group(1))

        if "src" in kwargs:
            src = kwargs["src"]
        else:
            m = re.search(r"@(oem|tle)", txt, flags=re.I)
            if m:
                src = m.group(1).lower()
            else:
                src = ws.config.get("satellites", "default_selector", fallback="tle")

        if "limit" in kwargs and "date" in kwargs:
            limit = kwargs["limit"]
            date = kwargs["date"]
        else:
            limit = "any"
            date = "any"
            m = re.search(r"(\^|\?)([0-9-T:.]+)", txt)
            if m:
                if m.group(1) == "^":
                    limit = "after"
                elif m.group(1) == "?":
                    limit = "before"

                try:
                    date = parse_date(m.group(2), fmt="date")
                except ValueError:
                    date = parse_date(m.group(2))

        return cls(selector, value, src, offset, limit, date)


class MyModel(Model):
    """Generic database object
    """

    class Meta:
        database = ws.db


class SatModel(MyModel):
    """Satellite object to interact with the database, not directly given to the
    user
    """

    norad_id = IntegerField(null=True)
    cospar_id = CharField(null=True)
    name = CharField()
    comment = TextField(null=True)

    def exists(self):
        return SatModel.select().where(SatModel.cospar_id == self.cospar_id).exists()

    class Meta:
        table_name = "sat"


class Alias(MyModel):
    name = CharField(unique=True)
    selector = CharField()


class Sat:
    def __init__(self, model):
        self.model = model
        self.orb = None
        self.req = None

    def __repr__(self):
        return "<Satellite '%s'>" % self.name

    @classmethod
    def from_orb(cls, orb):
        """From an Orbit or Ephem object
        """
        try:
            model = SatModel.select().where(SatModel.cospar_id == orb.cospar_id).get()
        except SatModel.DoesNotExist:
            model = SatModel(
                norad_id=getattr(orb, "norad_id", None),
                cospar_id=getattr(orb, "cospar_id", None),
                name=getattr(orb, "name", None),
            )

        if isinstance(orb, Tle):
            orb = orb.orbit()

        sat = cls(model)
        sat.orb = orb
        return sat

    @classmethod
    def from_selector(cls, *selector, **kwargs):
        """Method to parse a selector string such as 'norad=25544@oem~~'
        """
        for sel in selector:
            req = Request.from_text(sel, **kwargs)
            sat = cls._from_request(req, **kwargs)
            yield sat

    @classmethod
    def from_text(cls, text):
        """This method is used to parse an orbit from stdin
        """
        sats = [cls.from_orb(tle) for tle in Tle.from_string(text)]

        if not sats:
            try:
                orb = ccsds.loads(text)
            except ValueError:
                raise ValueError("No valid TLE nor CCSDS")
            else:
                if isinstance(orb, (Ephem, Orbit)):
                    sats = [cls.from_orb(orb)]
                else:
                    sats = [cls.from_orb(ephem) for ephem in orb]

        return sats

    @classmethod
    def from_input(cls, *selector, text="", alias=True, create=False, orb=True):

        sats = list(cls.from_selector(*selector, alias=alias, create=create, orb=orb))

        if not sats:
            if text:
                sats = cls.from_text(text)
            else:
                raise ValueError("No satellite found")

        return sats

    @classmethod
    def _from_request(cls, req, create=False, orb=True, type=None, **kwargs):
        # Retrieving the corresponding orbit or ephem object
        from .tle import TleDb, TleNotFound

        try:
            model = SatModel.select().filter(**{req.selector: req.value}).get()
        except SatModel.DoesNotExist:
            if create:
                model = SatModel(**{req.selector: req.value})
                model.save()
            else:
                raise ValueError(
                    "No satellite corresponding to {0.selector}={0.value}".format(req)
                )

        sat = cls(model)
        sat.req = req

        if orb:
            if type == "tle" or (type is None and sat.req.src == "tle"):
                if sat.req.limit == "any":
                    try:
                        tles = list(
                            TleDb().history(
                                **{sat.req.selector: sat.req.value},
                                number=sat.req.offset + 1
                            )
                        )
                    except TleNotFound:
                        raise NoDataError(sat.req)

                    if len(tles) <= sat.req.offset:
                        raise NoDataError(sat.req)

                    sat.orb = tles[0].orbit()
                else:
                    try:
                        tle = TleDb.get_dated(
                            limit=sat.req.limit,
                            date=sat.req.date.datetime,
                            **{sat.req.selector: sat.req.value}
                        )
                    except TleNotFound:
                        raise NoDataError(sat.req)
                    else:
                        sat.orb = tle.orbit()
            elif type == "oem" or (type is None and sat.req.src == "oem"):
                pattern = "*.{}".format(sat.req.src)
                if sat.folder.exists():
                    if sat.req.limit == "any":
                        try:
                            sat.orb = EphemDb(sat).get(offset=sat.req.offset)
                        except ValueError:
                            raise NoDataError(sat.req)
                    else:
                        try:
                            sat.orb = EphemDb(sat).get_dated(
                                limit=sat.req.limit, date=sat.req.date
                            )
                        except ValueError:
                            raise NoDataError(sat.req)
                else:
                    raise NoDataError(sat.req)

        return sat

    @property
    def name(self):
        return self.model.name

    @property
    def cospar_id(self):
        return self.model.cospar_id

    @property
    def norad_id(self):
        return self.model.norad_id

    @property
    def folder(self):
        year, idx = self.cospar_id.split("-")
        return ws.folder / "satdb" / year / idx


def sync(source="all"):
    """Update the database from the content of the TLE database and/or
    the Ephem database

    Args:
        source (str): 'all', 'tle', 'ephem'
    """

    sats = []

    if source in ("all", "tle"):
        from .tle import TleDb

        sats.extend(
            [
                SatModel(name=tle.name, cospar_id=tle.cospar_id, norad_id=tle.norad_id)
                for tle in TleDb().dump()
            ]
        )

    log.debug("{} satellites found in the TLE database".format(len(sats)))

    if source in ("all", "ephem"):
        folders = {}
        for folder in ws.folder.joinpath("satdb").glob("*/*"):
            cospar_id = "{}-{}".format(folder.parent.name, folder.name)
            folders[cospar_id] = list(folder.glob("*.oem"))

        # Filtering out satellites for which a TLE exists
        cospar_ids = set(folders.keys()).difference([sat.cospar_id for sat in sats])

        for cospar_id in cospar_ids:
            # print(cospar_id, folders[cospar_id])
            files = folders[cospar_id]
            if files:
                name = ccsds.load(files[0].open()).name
            else:
                name = "UNKNOWN"
                # log.debug()

            log.debug("Satellite '{}' ({}) found in ephem file".format(name, cospar_id))
            sats.append(SatModel(cospar_id=cospar_id, name=name))

    with ws.db.atomic():
        for sat in sats:
            if not sat.exists():
                sat.save()

    log.info("{} satellites registered".format(len(sats)))


def wshook(cmd, *args, **kwargs):

    if cmd in ("init", "full-init"):

        SatModel.create_table(safe=True)
        Alias.create_table(safe=True)

        if SatModel.select().exists():
            log.warning("SatDb already initialized")
        else:
            log.debug("Populating SatDb with TLE")
            sync()

        if not Alias.select().where(Alias.name == "ISS").exists():
            Alias(name="ISS", selector="norad_id=25544").save()
            log.info("Creating ISS alias")


def space_sat(*argv):
    """Get sat infos

    Usage:
      space-sat alias <alias> <selector> [--force]
      space-sat list-aliases
      space-sat orb <selector>
      space-sat sync
      space-sat infos <selector>

    Options:
      alias         Create an alias for quick access
      orb           Display the orbit corresponding to the selector
      list-aliases  List existing aliases
      sync          Update satellite database with existing TLEs
      infos         Display informations about a satellite
      <selector>    See below

    Satellite selectors
      ISS                : latest TLE of ISS
      norad=25544        : latest TLE of ISS selected by norad number
      cospar=2018-027A   : latest TLE of GSAT-6A
      ISS@oem            : latest OEM
      ISS@tle            : latest TLE
      ISS~               : before last TLE
      ISS~~              : 2nd before last TLE
      ISS@oem~25         : 25th before last OEM
      ISS@oem^2018-12-25 : first OEM after the date
      ISS@tle?2018-12-25 : first tle before the date
    """
    # TODO
    # ISS@opm            : latest OPM

    from .utils import docopt
    from .tle import space_tle
    from .ephem import space_ephem

    args = docopt(space_sat.__doc__, argv=argv)

    if args["alias"]:
        selector = args["<selector>"]
        name = args["<alias>"]

        try:
            sat = Sat.from_input(selector)
        except ValueError as e:
            log.error("Unknown satellite '{}'".format(selector))
            sys.exit(1)

        q = Alias.select().where(Alias.name == name)
        if q.exists():
            if args["--force"]:
                alias = q.get()
                alias.selector = selector
                alias.save()
                log.info("Alias '{}' ({}) created".format(name, selector))
            else:
                log.error(
                    "Alias '{}' already exists for '{}'".format(name, q.get().selector)
                )
                sys.exit()
        else:
            Alias(selector=selector, name=name).save()
            log.info("Alias '{}' ({}) created".format(name, selector))

    elif args["list-aliases"]:
        for alias in Alias:
            print("{:20} {}".format(alias.name, alias.selector))

    elif args["sync"]:
        sync()

    elif args["orb"]:
        try:
            sat = list(Sat.from_selector(args["<selector>"]))[0]
        except ValueError as e:
            log.error(e)
            sys.exit(1)

        if isinstance(sat.orb, Ephem):
            print(ccsds.dumps(sat.orb))
        else:
            print("{0.name}\n{0}".format(sat.orb.tle))

    elif args["infos"]:
        try:
            sat, = Sat.from_input(args["<selector>"], orb=False)
            print(
                """name       {0.name}
    cospar id  {0.cospar_id}
    norad id   {0.norad_id}
    folder     {0.folder}
    """.format(
                    sat
                )
            )
        except ValueError as e:
            log.error(e)
            sys.exit(1)
