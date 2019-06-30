import re
import sys
import logging
from textwrap import indent
from peewee import Model, IntegerField, CharField, SqliteDatabase, IntegrityError

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

    def __init__(self, orbdesc):
        self.od = orbdesc

    def __str__(self):
        return "No data for {od}".format(od=self.od)


class OrbDesc:
    """Request descriptor
    """

    def __init__(self, selector, value, src, last, limit, date):
        self.selector = selector
        self.value = value
        self.src = src
        self.last = last
        self.limit = limit
        self.date = date

    def __str__(self):

        txt = "{o.selector}={o.value}"

        if self.src is not None:
            txt += "@{o.src}"
        if self.last > 0:
            txt += "~{o.last}"

        return txt.format(o=self)


class parse_sats:
    """Parser of satellite description and input, both as command arguments and stdin
    """

    def __init__(self, *args, text=""):
        self.args = args
        self.text = text
        self.descs = [self.get_desc(txt) for txt in self.args]

        self.sats = []

        if self.descs:
            self.sats = [self._get_orb_from_desc(desc) for desc in self.descs]
        else:
            self.sats = [sat for sat in self.parse_orb(self.text)]

    def __iter__(self):
        return iter(self.sats)

    def __getitem__(self, key):
        return self.sats[key]

    @classmethod
    def parse_orb(self, text):
        sats = [SatOrb.from_orb(tle) for tle in Tle.from_string(text)]

        if not sats:
            try:
                orb = ccsds.loads(text)
            except ValueError:
                raise ValueError("No valid TLE nor CCSDS")
            else:
                if isinstance(orb, (Ephem, Orbit)):
                    sats = [SatOrb.from_orb(orb)]
                else:
                    sats = [SatOrb.from_orb(ephem) for ephem in orb]

        return sats

    @classmethod
    def get_desc(cls, txt, alias=True):
        # Parsing the string

        delimiters = r"[@~\^\?\$]"
        selector = re.split(delimiters, txt)[0]

        if alias:
            # Retrieve alias if it exists
            rq = Alias.select().where(Alias.name==selector)
            if rq.exists():
                selector = rq.get().selector

        if "=" in selector:
            k, v = selector.split('=')
            if k in ('norad', 'cospar'):
                k += "_id"
        else:
            k, v = "name", selector
        selector = k
        value = v

        last = 0
        if "~" in txt:
            last = txt.count("~")
            if last == 1:
                m = re.search(r"~(\d+)", txt)
                if m:
                    last = int(m.group(1))

        m = re.search(r"@(oem|tle)", txt, flags=re.I)
        if m:
            src = m.group(1).lower()
        else:
            src = ws.config.get('satellites', 'default_selector', fallback='tle')

        limit = "any"
        date = "any"
        m = re.search(r"(\^|\?)([0-9-T:.]+)", txt)
        if m:
            limit = "after" if m.group(1) == "^" else "before"
            try:
                date = parse_date(m.group(2), fmt='date')
            except ValueError:
                date = parse_date(m.group(2))

        return OrbDesc(selector, value, src, last, limit, date)

    @classmethod
    def _get_sat(cls, orbdesc):

        try:
            sat = Sat.select().filter(**{orbdesc.selector: orbdesc.value}).get()
        except Sat.DoesNotExist:
            raise ValueError("No satellite corresponding to {0.selector}={0.value}".format(orbdesc))
        else:
            sat = SatOrb(sat, None)

        sat.desc = orbdesc

        return sat

    @classmethod
    def _get_orb(cls, sat):

        # Retrieving the corresponding orbit or ephem object
        from .tle import TleDb, TleNotFound

        if sat.desc.src == "tle":
            if sat.desc.limit == "any":
                tles = list(TleDb().history(**{sat.desc.selector: sat.desc.value}, number=sat.desc.last + 1))
                if not tles:
                    raise NoDataError(sat.desc)
                if len(tles) <= sat.desc.last:
                    raise NoDataError(sat.desc)

                sat.orb = tles[0].orbit()
            else:
                try:
                    tle = TleDb.get_dated(limit=sat.desc.limit, date=sat.desc.date.datetime, **{sat.desc.selector: sat.desc.value})
                except TleNotFound:
                    raise NoDataError(sat.desc)
                else:
                    sat.orb = tle.orbit()
        else:
            pattern = "*.{}".format(sat.desc.src)
            if sat.folder.exists():
                if sat.desc.limit == "any":
                    try:
                        sat.orb = EphemDb(sat).get(last=sat.desc.last)
                    except ValueError:
                        raise NoDataError(sat.desc)
                else:
                    # TODO Implement date handling
                    pass
            else:
                raise NoDataError(sat.desc)

        return sat

    @classmethod
    def get_sat(cls, txt, **kwargs):
        return cls._get_sat(cls.get_desc(txt, **kwargs), **kwargs)

    @classmethod
    def _get_orb_from_desc(cls, desc, **kwargs):
        sat = cls._get_sat(desc, **kwargs)
        return cls._get_orb(sat, **kwargs)

    @classmethod
    def get_orb(cls, txt, **kwargs):
        desc = cls.get_desc(txt, **kwargs)
        return cls._get_orb_from_desc(desc, **kwargs)


class MyModel(Model):
    class Meta:
        database = ws.db


class Sat(MyModel):
    norad_id = IntegerField(unique=True)
    cospar_id = CharField()
    name = CharField()

    @classmethod
    def from_tle(cls, tle):
        return cls(
            name=tle.name,
            norad_id=tle.norad_id,
            cospar_id=tle.cospar_id,
        )


class Alias(MyModel):
    name = CharField(unique=True)
    selector = CharField()


class SatOrb:

    def __init__(self, sat, orb):
        self.sat = sat
        self.orb = orb

    def __repr__(self):
        return "<Satellite '%s'>" % self.name

    @classmethod
    def from_orb(cls, orb):
        try:
            sat = Sat.select().where(Sat.cospar_id == orb.cospar_id).get()
        except Sat.DoesNotExist:
            sat = Sat(
                norad_id=getattr(orb, 'norad_id', None),
                cospar_id=getattr(orb, 'cospar_id', None),
                name=getattr(orb, 'name', None)
            )

        if isinstance(orb, Tle):
            orb = orb.orbit()

        return cls(sat, orb)

    @property
    def name(self):
        return self.sat.name

    @property
    def cospar_id(self):
        return self.sat.cospar_id

    @property
    def norad_id(self):
        return self.sat.norad_id

    @property
    def folder(self):
        year, idx = self.cospar_id.split('-')
        return ws.folder / "satdb" / year / idx


def sync_tle():
    from .tle import TleDb
    sats = [Sat.from_tle(tle) for tle in TleDb().dump()]

    with ws.db.atomic():
        for sat in sats:
            try:
                sat.save()
            except IntegrityError:
                pass

    log.info("{} satellites registered".format(len(sats)))


def wshook(cmd, *args, **kwargs):

    if cmd in ('init', 'full-init'):

        Sat.create_table(safe=True)
        Alias.create_table(safe=True)

        if Sat.select().exists():
            log.warning("SatDb already initialized")
        else:
            log.debug("Populating SatDb with TLE")
            sync_tle()

        if not Alias.select().where(Alias.name=='ISS').exists():
            Alias(name="ISS", selector="norad_id=25544").save()
            log.info("Creating ISS alias")


def space_sat(*argv):
    """Get sat infos

    Usage:
      space-sat alias <alias> <selector> [--force]
      space-sat list-aliases
      space-sat orb <selector>
      space-sat sync-tle

    Options:
      alias         Create an alias for quick access
      orb           Display the orbit corresponding to the selector
      list-aliases  List existing aliases
      sync-tle      Update satellite database with existing TLEs
      <selector>    See below

    Satellite selectors
      ISS                : latest TLE if ISS
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

    if args['alias']:
        selector = args['<selector>']
        name = args['<alias>']

        try:
            sat = parse_sats.get_sat(selector)
        except ValueError as e:
            log.error("Unknown satellite '{}'".format(selector))
            sys.exit(-1)

        q = Alias.select().where(Alias.name == name)
        if q.exists():
            if args['--force']:
                alias = q.get()
                alias.selector = selector
                alias.save()
                log.info("Alias '{}' ({}) created".format(name, selector))
            else:
                log.error("Alias '{}' already exists for '{}'".format(name, q.get().selector))
                sys.exit()
        else:
            Alias(selector=selector, name=name).save()
            log.info("Alias '{}' ({}) created".format(name, selector))

    elif args['list-aliases']:
        for alias in Alias:
            print("{:20} {}".format(alias.name, alias.selector))

    elif args['sync-tle']:
        sync_tle()

    elif args['orb']:
        try:
            sat = parse_sats.get_orb(args['<selector>'])
        except ValueError as e:
            log.error(e)
            sys.exit(-1)

        if isinstance(sat.orb, Ephem):
            print(ccsds.dumps(sat.orb))
        else:
            tle = Tle.from_orbit(
                sat.orb,
                norad_id=sat.norad_id,
                cospar_id=sat.cospar_id,
                name=sat.name
            )
            print("{0.name}\n{0}".format(tle))
