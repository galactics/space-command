import re
import sys
import logging
from textwrap import indent
from peewee import Model, IntegerField, CharField, SqliteDatabase, IntegrityError

from beyond.dates import Date, timedelta
from beyond.orbits import Ephem, Orbit
import beyond.io.ccsds as ccsds
from beyond.io.tle import Tle
from beyond.propagators import get_propagator
from beyond.env.solarsystem import get_body

from .config import config

log = logging.getLogger(__name__)


class NoDataError(Exception):

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

        delimiters = r"[@~$\?]"
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

        src = None
        m = re.search(r"@(oem|tle)", txt, flags=re.I)
        if m:
            src = m.group(1).lower()
        else:
            src = config.get('satellites', 'default_selector', fallback='tle')

        limit = "any"
        date = "any"
        m = re.search(r"(\^|\?)([0-9-T:.]+)", txt)
        if m:
            limit = "after" if m.group(1) == "^" else "before"
            date = Date.strptime(m.group(2), "%Y-%m-%d")

        return OrbDesc(selector, value, src, last, limit, date)

    @classmethod
    def _get_sat(cls, orbdesc):

        # Retrieving the corresponding orbit or ephem object
        try:
            sat = Sat.select().filter(**{orbdesc.selector: orbdesc.value}).get()
        except Sat.DoesNotExist:
            raise ValueError("No satellite corresponding to {0.selector}={0.value}".format(orbdesc))
        else:
            sat = SatOrb(sat, None)

        return sat

    @classmethod
    def _get_orb(cls, orbdesc, sat):

        from .tle import TleDb, TleNotFound

        if orbdesc.src == "tle":
            if orbdesc.limit == "any":
                tles = list(TleDb().history(**{orbdesc.selector: orbdesc.value}, number=orbdesc.last + 1))
                if not tles:
                    raise NoDataError(orbdesc)
                if len(tles) <= orbdesc.last:
                    raise NoDataError(orbdesc)

                sat.orb = tles[0].orbit()
            else:
                # TODO Implement date handling
                pass
        else:
            pattern = "*.{}".format(orbdesc.src)
            if sat.folder.exists():
                if orbdesc.limit == "any":
                    files = list(sorted(sat.folder.glob(pattern)))
                    if not files:
                        raise NoDataError(orbdesc)
                    if len(files) <= orbdesc.last:
                        raise NoDataError(orbdesc)
                    sat.orb = ccsds.load(files[-(1+orbdesc.last)].open())

                    # if isinstance(sat.orb, Orbit):
                    #     propagator_cls = get_propagator(config.get('satellites', 'opm', 'default_propagator', 'name', fallback='Kepler'))
                    #     step = timedelta(seconds=config.get('satellites', 'opm', 'default_propagator', 'step', fallback=10))
                    #     bodies = get_body(config.get('satellites', 'opm', 'default_propagator', 'bodies', fallback='Earth'))
                    #     sat.orb.propagator = propagator_cls(step, bodies)
                else:
                    # TODO Implement date handling
                    pass
            else:
                raise NoDataError(orbdesc)

        # print("selector ", selector)
        # print("last     ", last)
        # print("src      ", src)
        # print("limit    ", limit)
        # print("date     ", date)

        return sat

    @classmethod
    def get_sat(cls, txt, **kwargs):
        return cls._get_sat(cls.get_desc(txt, **kwargs), **kwargs)

    @classmethod
    def _get_orb_from_desc(cls, desc, **kwargs):
        sat = cls._get_sat(desc, **kwargs)
        return cls._get_orb(desc, sat, **kwargs)

    @classmethod
    def get_orb(cls, txt, **kwargs):
        desc = cls.get_desc(txt, **kwargs)
        return cls._get_orb_from_desc(descs, **kwargs)


def db():
    if not hasattr(db, '_instance'):
        db._instance = SqliteDatabase(None)
        db._instance.init(str(config.folder / "space.db"))

    return db._instance


class Sat(Model):
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

    class Meta:
        database = db()


class Alias(Model):
    name = CharField(unique=True)
    selector = CharField()

    class Meta:
        database = db()


class SatOrb:

    def __init__(self, sat, orb):
        self.sat = sat
        self.orb = orb

    def __repr__(self):
        return "<Satellite '%s'>" % self.name

    @classmethod
    def from_orb(cls, orb):
        sat = Sat.select().where(Sat.cospar_id == orb.cospar_id).get()

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
        return config.folder / "satdb" / year / idx

    def list(self, src='tle'):
        if src == 'tle':
            from .tle import TleDb
            return list(reversed(list(TleDb().history(cospar_id=self.cospar_id))))
        # elif src in ('oem', 'opm'):
        elif src == 'oem':
            return [ccsds.load(orb.open()) for orb in reversed(list(self.folder.glob("*.{}".format(src))))]
        else:
            raise ValueError('Unknown source')

    def list_all(self):
        tles = self.list('tle')
        # opms = self.list('opm')
        oems = self.list('oem')

        def sort(o):
            if isinstance(o, Orbit):
                return o.date
            elif isinstance(o, Tle):
                return o.epoch
            else:
                return o.start

        data = {}
        for orb in sorted(tles + oems, key=sort):
            yield orb

    def save(self, force=False):
        if not self.folder.exists():
            self.folder.mkdir(parents=True)

        if isinstance(self.orb, Ephem):
            filename = "{self.cospar_id}_{self.orb.start:%Y%m%d_%H%M%S}.oem".format(self=self)
        # elif isinstance(self.orb, Orbit):
        #     filename = "{self.cospar_id}_{self.orb.date:%Y%m%d_%H%M%S}.opm".format(self=self)

        filepath = self.folder / filename

        if filepath.exists() and not force:
            raise FileExistsError(filepath)

        with filepath.open('w') as fp:
            ccsds.dump(self.orb, fp)

        log.info("{} saved".format(filepath))


def sync_tle():
    from .tle import TleDb
    sats = [Sat.from_tle(tle) for tle in TleDb().dump()]

    with db().atomic():
        for sat in sats:
            try:
                sat.save()
            except IntegrityError:
                pass

    log.info("{} satellites registered".format(len(sats)))


def space_sat(*args):
    """Get sat infos

    Usage:
      space-sat insert (- | <file>) [--force]
      space-sat alias <alias> <selector> [--force]
      space-sat list-aliases
      space-sat list-orbs <selector>
      space-sat orb <selector>
      space-sat sync-tle

    Options:
      insert        Add TLEs from file or stdin
      alias         Create an alias for quick access
      list-aliases  List existing aliases
      list-orbs     List available orbit files (TLE or OEM)
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
    """
    # TODO
    # ISS@opm            : latest OPM
    # ISS@oem^2018-12-25 : first OEM after the date
    # ISS@tle?2018-12-25 : first tle before the date

    from .utils import docopt

    args = docopt(space_sat.__doc__)

    if args['insert']:
        if args['-'] and not sys.stdin.isatty():
            txt = sys.stdin.read()
        else:
            txt = open(args['<file>']).read()

        for sat in parse_sats.parse_orb(txt):
            try:
                sat.save(args['--force'])
            except FileExistsError as e:
                log.error("{} already exists".format(e))

    elif args['alias']:
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
        satorb = parse_sats.get_orb(args['<selector>'])
        print(repr(satorb.orb))

    else:
        try:
            orbdesc = parse_sats.get_desc(args['<selector>'])
            sat = parse_sats._get_sat(orbdesc)
        except ValueError as e:
            log.error(e)
            sys.exit(-1)

        fmt = "%Y-%m-%dT%H:%M:%S"

        print("       Date/Start           Stop")
        print("-"*50)
        if orbdesc.src is None:
            for orb in list(sat.list_all())[-18:]:
                if isinstance(orb, Ephem):
                    print("  OEM  {orb.start:{fmt}}  {orb.stop:{fmt}}".format(orb=orb, fmt=fmt))
                # elif isinstance(orb, Orbit):
                #     print("OPM  {orb.date:{fmt}}".format(orb=orb, fmt=fmt))
                else:
                    print("  TLE  {orb.epoch:{fmt}}".format(orb=orb, fmt=fmt))
        else:
            orbs = list(reversed(list(sat.list(orbdesc.src))[:18]))
            for i, orb in enumerate(orbs):

                s = ">" if len(orbs) - i - 1 == orbdesc.last else ""

                if isinstance(orb, Ephem):
                    print("{s:1} OEM  {orb.start:{fmt}}  {orb.stop:{fmt}}".format(s=s, orb=orb, fmt=fmt))
                # elif isinstance(orb, Orbit):
                #     print("OPM  {orb.date:{fmt}}".format(orb=orb, fmt=fmt))
                else:
                    print("{s:1} TLE  {orb.epoch:{fmt}}".format(s=s, orb=orb, fmt=fmt))
