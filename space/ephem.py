import sys
import logging
from datetime import timedelta

from beyond.config import config
import beyond.io.ccsds as ccsds
from beyond.orbits import Ephem

from .clock import Date
from .station import StationDb
from .utils import parse_date, parse_timedelta

log = logging.getLogger(__name__)


class EphemDb:

    EXT = "oem"

    def __init__(self, sat):
        self.sat = sat

    @property
    def pattern(self):
        return "*.{}".format(self.EXT)

    def list(self):
        for orb in sorted(list(self.sat.folder.glob(self.pattern)), reverse=True):
            yield ccsds.load(orb.open())

    def insert(self, orb, force=False):
        if not self.sat.folder.exists():
            self.sat.folder.mkdir(parents=True)

        filename = "{sat.cospar_id}_{orb.start:%Y%m%d_%H%M%S}.{ext}".format(
            sat=self.sat, orb=orb, ext=self.EXT
        )
        filepath = self.sat.folder / filename

        if filepath.exists() and not force:
            log.error("The file {} already exists".format(filepath))
            raise FileExistsError(filepath)

        with filepath.open("w") as fp:
            ccsds.dump(orb, fp)

        log.info("{} saved".format(filepath))

    def get(self, offset=0):
        files = list(sorted(self.sat.folder.glob(self.pattern)))

        if not files or len(files) <= offset:
            raise ValueError()

        return ccsds.load(files[-(1 + offset)].open())

    def get_dated(self, limit, date):

        reverse = False
        if limit == "before":
            func = "__lt__"
            reverse = True
        else:
            func = "__gt__"

        for file in sorted(self.sat.folder.glob(self.pattern), reverse=reverse):
            mtime = Date.strptime(file.stem.partition("_")[2], "%Y%m%d_%H%M%S")
            if getattr(mtime, func)(date):
                break
        else:
            raise ValueError("No ephemeris found")

        return ccsds.load(file.open())


def space_ephem(*argv):  # pragma: no cover
    """Compute ephemeris from a given TLE

    Usage:
        space-ephem get <selector>...
        space-ephem insert (- | <file>)
        space-ephem compute (- | <selector>...) [options]
        space-ephem list <selector>... [options]

    Option
        get                   Retrieve an existing ephemeris from the database
        list                  List existing ephemerides
        compute               Compute ephemeris from a TLE
        insert                Insert a ephemeris into the database
        <selector>            Selector of the satellite
        -f, --frame <frame>   Frame in which to write the file to
        -d, --date <date>     Start date of the ephem [default: midnight]
                              (format %Y-%m-%dT%H:%M:%S)
        -r, --range <days>    Duration of extrapolation [default: 3d]
        -s, --step <step>     Step size of the ephemeris [default: 180s]
        -i, --interp <inter>  Interpolation method (linear, lagrange) [default: lagrange]
        --insert              Insert the computed ephemeris into the database
        --force               Force insertion
        -l, --last <last>     When listing print the last N ephems [default: 10]
    """

    from .utils import docopt
    from .sat import Sat

    args = docopt(space_ephem.__doc__, argv=argv)

    if args["compute"]:

        try:
            start = parse_date(args["--date"])
            stop = parse_timedelta(args["--range"])
            step = parse_timedelta(args["--step"])
            satlist = Sat.from_input(
                *args["<selector>"], text=sys.stdin.read() if args["-"] else ""
            )
        except ValueError as e:
            log.error(e)
            sys.exit(1)

        ephems = []
        for sat in satlist:
            ephem = sat.orb.ephem(start=start, stop=stop, step=step)
            ephem.name = sat.name
            ephem.cospar_id = sat.cospar_id
            ephem.method = args["--interp"]
            if args["--frame"] is not None:
                ephem.frame = StationDb.get(args["--frame"])

            ephems.append(ephem)

        txt = ccsds.dumps(
            ephems, originator=config.get("center", "name", fallback="N/A")
        )

        print(txt)
        print("")

    if args["insert"] or (args["compute"] and args["--insert"]):

        if args["--insert"]:
            pass
        elif args["-"] and not sys.stdin.isatty():
            txt = sys.stdin.read()
        else:
            txt = open(args["<file>"]).read()

        try:
            sats = Sat.from_input(text=txt, create=True)
        except ValueError as e:
            log.error(e)
            sys.exit(1)

        for sat in sats:
            db = EphemDb(sat)
            try:
                db.insert(sat.orb, args["--force"])
            except FileExistsError as e:
                continue
    elif args["list"]:

        max_idx = int(args["--last"])

        try:
            for sat in Sat.from_selector(*args["<selector>"], type="oem"):

                print(sat.name)
                print("idx  Start                Stop                 Steps")
                print("-" * 55)
                print(sat.req)

                for idx, ephem in enumerate(EphemDb(sat).list()):

                    if (
                        sat.req.limit == "any"
                        and idx == sat.req.offset
                        or ephem.start == sat.orb.start
                    ):
                        color = "* \033[32m"
                        endcolor = "\033[39m"
                    else:
                        color = "  "
                        endcolor = ""

                    if idx >= max_idx:
                        break

                    steps = set()
                    for orb_i, orb_j in zip(ephem[:-1], ephem[1:]):
                        steps.add(orb_j.date - orb_i.date)

                    if len(steps) == 1:
                        steps, = steps
                    else:
                        steps = "[{}, {}]".format(min(steps), max(steps))

                    print(
                        "{color}{idx:<2} {ephem.start:{fmt}}  {ephem.stop:{fmt}}  {steps}{endcolor}".format(
                            idx=idx,
                            ephem=ephem,
                            fmt="%Y-%m-%dT%H:%M:%S",
                            steps=steps,
                            color=color,
                            endcolor=endcolor,
                        )
                    )
                print()
        except ValueError as e:
            log.error(e)
            sys.exit(1)

    elif args["get"]:
        ephems = []
        try:
            for sat in Sat.from_selector(*args["<selector>"], src="oem"):
                if not isinstance(sat.req.date, Date):
                    ephem = EphemDb(sat).get(offset=sat.req.offset)
                else:
                    ephem = EphemDb(sat).get_dated(
                        date=sat.req.date, limit=sat.req.limit
                    )
                ephems.append(ephem)
        except ValueError as e:
            log.error(e)
            sys.exit(1)

        print(ccsds.dumps(ephems))
