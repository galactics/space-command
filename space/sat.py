import re
import sys
import logging
from peewee import (
    Model,
    IntegerField,
    CharField,
    TextField,
)

from beyond.orbits import Ephem, Orbit
from beyond.io.tle import Tle

from .clock import Date
from .utils import parse_date
from .wspace import ws
from .ccsds import CcsdsDb
from . import ccsds

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

    def __repr__(self):
        return """Request:
  selector: {self.selector}
  value: {self.value}
  src: {self.src}
  offset: {self.offset}
  limit: {self.limit}
  date: {self.date}
""".format(
            self=self
        )

    @classmethod
    def from_text(cls, txt, alias=True, **kwargs):
        """Convert a strin 'cospar=1998-067A@tle~~' to a Request object

        Any kwargs matching Request object attributes will override the text value
        For example ``Request.from_text("ISS@tle", src='oem')`` will deliver a
        request object with ``req.src == 'oem'``.

        Inseparable pairs are selector/value and limit/date respectively
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
            m = re.search(r"@([a-zA-Z0-9]+)", txt, flags=re.I)
            if m:
                src = m.group(1).lower()
            else:
                src = ws.config.get("satellites", "default-orbit-type", fallback="tle")

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
    def from_selector(cls, string, **kwargs):
        """Method to parse a selector string such as 'norad=25544@oem~~'

        This method is oriented toward developers, to allow them to access
        quickly and simply an orbital object.

        Args:
            string (str): Selector string
        Keyword Args:
            temporary (bool) : if True, a Sat object is created even if there is no match
                for the request in the database. This Sat object is not saved into the database.
                False by default.
            save (bool) : if True, a Sat object is created even if there is no match
                for the request in the database. This Sat object is then saved into the database.
                False by default.
            orb (bool) : if False, do not retrieve the orbital data associated with the request.
                True by default.
            alias (bool) : if False, disable aliases lookup. True by default.
        Return:
            Sat

        Any field of the selector string can be overridden by its associated
        keyword argument.

        Keyword Args:
            selector (str) : "name", "cospar" or "norad"
            value (str) : The value associated with the selector
            offset (int) : offset of orbital data to retrieve. for example offset=1 will get you
                the first before last orbital data available
            src (str) : Orbital data source ("oem", "opm" or "tle")
            limit (str) : Date action. "after", "before" or "any"
            date (Date) : 

        Example:
            # retrieve the latest TLE of the ISS
            Sat.from_selector("ISS@tle")
            # retrieve the first TLE of the year (after 2020-01-01 at midnight)
            Sat.from_selector("ISS@tle^2020-01-01")
        """
        req = Request.from_text(string, **kwargs)
        return cls._from_request(req, **kwargs)

    @classmethod
    def from_selectors(cls, *selectors, **kwargs):
        """Retrieve multiples sa
        """
        for sel in selectors:
            yield cls.from_selector(sel, **kwargs)

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
    def from_command(cls, *selector, text="", **kwargs):
        """This method is intended to be used as parser of command line arguments
        to handle both selector strings ("norad=25544@tle~32") as well as stdin
        inputs.

        The canonical way to use this method is:

            Sat.from_command(
                *args["<satellite>"],
                text=sys.stdin.read() if args["-"] else ""
            )

        see :py:meth:`Sat.from_selector` for the others keyword arguments
        """

        sats = list(cls.from_selectors(*selector, **kwargs))

        if not sats:
            if text:
                sats = cls.from_text(text)
            else:
                raise ValueError("No satellite found")

        return sats

    @classmethod
    def _from_request(cls, req, create=False, temporary=False, orb=True, **kwargs):
        """This method convert a Request object to a Sat object with the
        associated orbital data (TLE, OEM or OPM)
        """

        if create or temporary:
            orb = False

        from .tle import TleDb, TleNotFound

        try:
            model = SatModel.select().filter(**{req.selector: req.value}).get()
        except SatModel.DoesNotExist:
            if temporary or create:
                model = SatModel(**{req.selector: req.value})
                if create:
                    model.save()
            else:
                raise ValueError(
                    "No satellite corresponding to {0.selector}={0.value}".format(req)
                )

        sat = cls(model)
        sat.req = req

        if orb:
            if sat.req.src == "tle":
                if sat.req.limit == "any":
                    try:
                        tles = list(
                            TleDb().history(
                                **{sat.req.selector: sat.req.value},
                                number=sat.req.offset + 1,
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
                            **{sat.req.selector: sat.req.value},
                        )
                    except TleNotFound:
                        raise NoDataError(sat.req)
                    else:
                        sat.orb = tle.orbit()
            elif sat.req.src in ("oem", "opm"):
                pattern = "*.{}".format(sat.req.src)
                if sat.folder.exists():
                    try:
                        sat.orb = CcsdsDb.get(sat)
                    except ValueError:
                        raise NoDataError(sat.req)
                else:
                    raise NoDataError(sat.req)
            else:
                tags = CcsdsDb.tags(sat)
                if sat.req.src in tags.keys():
                    sat.orb = ccsds.load(tags[sat.req.src].open())
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

    new = []
    update = []

    if source in ("all", "tle"):
        from .tle import TleDb

        # The resoning of the Tle Database is by NORAD ID
        all_sats = {sat.norad_id: sat for sat in SatModel.select()}

        for tle in TleDb().dump():
            if tle.norad_id not in all_sats:
                sat = SatModel(
                    name=tle.name, cospar_id=tle.cospar_id, norad_id=tle.norad_id
                )
                new.append(sat)
                log.debug(
                    "{sat.norad_id} added (name='{sat.name}' cospar_id='{sat.cospar_id}')".format(
                        sat=sat
                    )
                )
            else:
                sat = all_sats[tle.norad_id]
                if tle.name != sat.name or tle.cospar_id != sat.cospar_id:
                    log.debug(
                        "{sat.norad_id} updated. name='{sat.name}'-->'{tle.name}' cospar_id='{sat.cospar_id}'-->'{tle.cospar_id}' ".format(
                            sat=sat, tle=tle
                        )
                    )
                    sat.name = tle.name
                    sat.cospar_id = tle.cospar_id
                    update.append(sat)

    log.debug("{} new satellites found in the TLE database".format(len(new)))
    log.debug("{} satellites to update from the TLE database".format(len(update)))

    new_idx = 0
    if source in ("all", "ephem"):

        # The organization of the ephem database is by COSPAR ID
        all_sats = {sat.cospar_id: sat for sat in SatModel.select()}

        folders = {}
        for folder in ws.folder.joinpath("satdb").glob("*/*"):
            cospar_id = "{}-{}".format(folder.parent.name, folder.name)
            folders[cospar_id] = list(folder.glob("*.oem"))

        # Filtering out satellites for which an entry in the Sat DB already exists
        cospar_ids = set(folders.keys()).difference(all_sats.keys())

        for cospar_id in cospar_ids:
            # print(cospar_id, folders[cospar_id])
            files = folders[cospar_id]
            if files:
                name = ccsds.load(files[0].open()).name
            else:
                name = "UNKNOWN"
                # log.debug()

            log.debug(
                "New satellite '{}' ({}) found in ephem file".format(name, cospar_id)
            )
            new.append(SatModel(cospar_id=cospar_id, name=name))
            new_idx += 1

        if not cospar_ids:
            log.debug("{} new satellites found in ephem files".format(new_idx))

    with ws.db.atomic():
        for sat in update + new:
            sat.save()

    log.info(
        "{} new satellites registered, {} satellites updated".format(
            len(new), len(update)
        )
    )


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
      ISS@tle?2018-12-25 : first TLE before the date
    """
    # TODO
    # ISS@opm            : latest OPM

    from .utils import docopt

    args = docopt(space_sat.__doc__, argv=argv)

    if args["alias"]:
        selector = args["<selector>"]
        name = args["<alias>"]

        try:
            sat = Sat.from_selector(selector, orb=False)
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
            sat = Sat.from_selector(args["<selector>"])
        except ValueError as e:
            log.error(e)
            sys.exit(1)

        if hasattr(sat.orb, "tle"):
            print("{0.name}\n{0}".format(sat.orb.tle))
        else:
            print(ccsds.dumps(sat.orb))

    elif args["infos"]:
        try:
            (sat,) = Sat.from_command(args["<selector>"], orb=False)
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
