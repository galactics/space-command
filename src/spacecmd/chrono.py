
import curses
import numpy as np
from datetime import timedelta

from beyond.utils import Date
from beyond.config import config
from beyond.orbits.listeners import LightListener

from .stations import get_station
from .satellites import Satellite


class Pass:

    def __init__(self, satellite, station):
        self.satellite = satellite
        self.station = station
        self.max = (0, 0)


class Curses:

    def __init__(self, height):
        self.height = height

    def __enter__(self):
        self.scr = curses.initscr()
        curses.echo()
        curses.cbreak()
        curses.halfdelay(10)
        curses.curs_set(0)
        self.scr.keypad(True)
        self.scr.clear()

        self.pad = curses.newpad(100, 80)
        # pad = curses.newpad(self.height + 5, 80)

        return self.pad

    def __exit__(self, type, value, traceback):
        curses.nocbreak()
        self.scr.keypad(False)
        curses.echo()
        curses.endwin()

    def update(self):
        curses.update_lines_cols()
        self.pad.refresh(0, 0, 0, 0, curses.LINES - 1, curses.COLS - 1)


def visi(sat, sta, start, stop, step, threshold=10):
    tle = sat.tle()
    p = Pass(sat, sta)
    passes = []

    for orb in sta.visibility(tle, start, stop, step, events=True):

        if orb.info:
            elev = np.degrees(orb.phi)
            azim = -np.degrees(orb.theta) % 360

            attr = orb.date if orb.info.startswith("AOS") or orb.info.startswith("LOS") else (elev, azim)
            setattr(p, orb.info.lower().split()[0], attr)

            if orb.info.startswith("LOS") and hasattr(p, 'aos'):
                if p.max[0] >= threshold:
                    passes.append(p)
                p = Pass(sat, sta)

    return passes


def compute_pass(pass_obj, step):
    pass_details = []
    tle = pass_obj.satellite.tle()

    for orb in pass_obj.station.visibility(tle, start=pass_obj.aos - step, stop=timedelta(hours=24), step=step, events=True):
        pass_details.append(orb)
        if orb.info.startswith("LOS"):
            return pass_details


def live_pass(scr, pass_obj):

    scr.clear()
    step = timedelta(seconds=30)

    pass_details = compute_pass(pass_obj, step)

    light = LightListener()

    while True:

        now = Date.now()

        scr.addstr(0, 0, "{p.satellite.name} {p.station.abbr}  {d:%H:%M:%S}".format(p=pass_obj, d=now))
        scr.addstr(1, 0, "         Time      Azim    Elev    Dist (km) Radial Velocity (m.s⁻¹)")
        scr.addstr(2, 0, "====================================================================")

        for i, orb in enumerate(pass_details):

            fmt = 0
            if pass_obj.aos <= now <= pass_obj.los and orb.date <= now < pass_details[i + 1].date:
                fmt = curses.A_REVERSE

            azim = -np.degrees(orb.theta) % 360
            elev = np.degrees(orb.phi)
            r = orb.r / 1000.
            scr.addstr(i + 3, 0, "{orb.info:7} {orb.date:%H:%M:%S} {azim:7.2f} {elev:7.2f} {r:10.2f} {orb.r_dot:10.2f} {light}".format(orb=orb, r=r, azim=azim, elev=elev, light=light.info(orb)), fmt)

        curses.update_lines_cols()
        scr.refresh(0, 0, 0, 0, curses.LINES - 1, curses.COLS - 1)
        key = scr.getch()

        if key in (ord("q"), ord("Q")):
            return
        elif key in(ord('h'), ord('H')):
            live_help(scr)


def live_help(scr):

    scr.clear()
    scr.addstr(0, 0, "Help space-chrono")
    scr.addstr(1, 0, "=================")
    scr.addstr(3, 0, "Controls:")
    scr.addstr(4, 0, "---------")

    scr.addstr(5, 1, "up, down: Select a pass and view details")
    scr.addstr(6, 1, "h:        Display this help")
    scr.addstr(7, 1, "q:        Return to previous panel")

    curses.update_lines_cols()
    scr.refresh(0, 0, 0, 0, curses.LINES - 1, curses.COLS - 1)

    while True:
        key = scr.getch()
        if key in (ord("q"), ord("Q")):
            scr.clear()
            break


def live_chrono(scr, sta, passes):

    selected = 0
    while True:

        key = scr.getch()

        if key in (ord("q"), ord("Q")):
            break
        elif key == ord("B"):
            selected += 1
        elif key == ord("A"):
            selected -= 1
        elif key in (ord("h"), ord("H")):
            live_help(scr)
        elif key == 10:
            live_pass(scr, passes[selected])

        if selected < 0:
            selected = 0
        elif selected >= len(passes):
            selected = len(passes) - 1

        next_pass = False
        now = Date.now()
        scr.clear()
        scr.addstr(0, 10, "{} {:%Y-%m-%d %H:%M:%S}".format(sta.abbr, now))
        scr.addstr(2, 2, " sat         AOS       LOS       dur Max   ETA")
        scr.addstr(3, 1, "========================================================")
        for i, p in enumerate(passes):
            mark = ""
            fmt = 0
            if p.aos <= now <= p.los:
                fmt = curses.A_REVERSE
            elif p.aos > now and not next_pass:
                next_pass = True

            scr.addstr(
                i + 4, 3,
                "{p.satellite.name:<10}  {p.aos:%H:%M:%S}  {p.los:%H:%M:%S}  {duration:2d}  {p.max[0]:4.1f}  {timer}".format(
                    p=p, mark=mark,
                    duration=int((p.los - p.aos).total_seconds() / 60.),
                    timer="AOS-%s" % str(p.aos - now)[:-7] if next_pass else ""
                ),
                fmt
            )

        scr.addstr(selected + 4, 1, ">")

        curses.update_lines_cols()
        scr.refresh(0, 0, 0, 0, curses.LINES - 1, curses.COLS - 1)


def spacecmd_chrono(*argv):
    """\
    Compute available passes for the day

    Usage:
        space-chrono <station> [-t <thresh>] [--live] [-d <days>] [-s <sat>] [-n]

    Options:
        <station>       Station for which to compute the passes
        -t <thresh>  Minimun angle to keep a pass [default: 10]
        -l, --live      Dynamic display
        -d <days>       How long should be the prediction (in days) [default: 0.5]
        -s <sat>        Only for the desired satellite
        -n, --no-cache  Disable cache
    """

    import sys
    from docopt import docopt
    from textwrap import dedent
    from multiprocessing import Pool
    import pickle

    args = docopt(dedent(spacecmd_chrono.__doc__), argv=argv)

    try:
        sta = get_station(args['<station>'])
    except ValueError:
        print("Unknown station '%s'" % args['<station>'])
        sys.exit(-1)

    cache_filepath = config['folder'] / ("chrono_%s.pkl" % sta.name)
    start = Date.now() - timedelta(minutes=15)
    stop = timedelta(days=float(args['-d']))
    step = timedelta(seconds=180)
    threshold = float(args['-t'])

    if args['--no-cache']:
        cache = None
    else:
        try:
            with open(cache_filepath, 'rb') as fp:
                cache = pickle.load(fp)
        except:
            cache = None

    if not cache or cache[0].aos + timedelta(minutes=30) < Date.now():
        print("Computing passes")
        satlist = Satellite.get_all() if args['-s'] is None else [Satellite.get(name=args['-s'])]

        with Pool(processes=int(config.get('multiprocessing', 'processes', 1))) as pool:

            mp_args = []
            for sat in sorted(satlist, key=lambda x: x.name):
                mp_args.append([sat, sta, start, stop, step, threshold])

            passes = pool.starmap(visi, mp_args)

        # Flattening of the passes and sorting them by AOS
        passes = sorted([y for x in passes for y in x], key=lambda x: x.aos)

        with open(cache_filepath, 'wb') as fp:
            pickle.dump(passes, fp)
    else:
        passes = cache

    if not args['--live']:
        mark = "   "
        print("           {} {:%Y-%m-%d %H:%M:%S}".format(sta.abbr, Date.now()))
        print(" sat        AOS       LOS        dur Max")
        print("==========================================")
        for i, p in enumerate(passes):
            print(
                " {p.satellite.name:<10}  {p.aos:%H:%M:%S}  {p.los:%H:%M:%S}  {duration:2d}  {p.max[0]:4.1f}".format(
                    p=p, mark=mark, duration=int((p.los - p.aos).total_seconds() / 60)
                ),
            )
    else:
        try:
            with Curses(len(passes)) as scr:
                live_chrono(scr, sta, passes)

        except KeyboardInterrupt:
            print("Fin")
