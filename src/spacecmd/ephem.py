
from datetime import timedelta

from beyond.config import config
from beyond.utils import Date
from beyond.utils.ccsds import CCSDS

from .satellites import Satellite


def get_ephem_path(name):
    return config['folder'] / 'ephem' / ('%s.oem' % name)


def get_ephem(name):
    return CCSDS.load(get_ephem_path(name))


def create_ephem(sat, start, stop, step, frame=None, interp=None):
    try:
        orb = sat.tle()
    except KeyError:
        print("{:<10} not found".format(sat.name))
    else:
        ephem = orb.ephem(start, stop, step)
        ephem.method = interp
        if frame is not None:
            ephem.frame = frame

        ephem_path = get_ephem_path(sat.name)

        if not ephem_path.parent.exists():
            ephem_path.parent.mkdir()

        CCSDS.dump(
            ephem,
            get_ephem_path(sat.name),
            name=sat.name,
            cospar_id=sat.cospar_id,
            originator=config.get('center', 'name', "Unknown")
        )
        print("{:<10} OK".format(sat.name))


def spacecmd_ephem(*argv):
    """\
    Compute ephemeris for a given TLE

    Usage:
        space-ephem <name> [-f <frame>] [-i <inter>] [-s <date>] [-r <days>] [-t <step>]

    Option
        <name>                Name of the object
        -f, --frame <frame>   Frame in which to write the file to
        -s, --start <date>    Date in format %Y-%m-%d, today at midnight if absent
        -r, --range <days>    Duration of extrapolation [default: 3]
        -t, --step <step>     Step size of the ephemeris in sec. [default: 180]
        -i, --interp <inter>  Interpolation method (linear, lagrange) [default: lagrange]
    """

    from docopt import docopt
    from textwrap import dedent
    from multiprocessing import Pool

    args = docopt(dedent(spacecmd_ephem.__doc__), argv=argv)

    if args['--start'] is None:
        start = Date(Date.now().d)
    else:
        start = Date.strptime(args["--start"], "%Y-%m-%d")

    stop = timedelta(days=float(args['--range']))
    step = timedelta(seconds=float(args['--step']))

    name = args['<name>']
    if name == 'ALL':
        sats = Satellite.get_all()
    else:
        sats = [Satellite.get(name=name)]

    with Pool(processes=int(config.get('multiprocessing', 'processes', 1))) as pool:
        pool.starmap(create_ephem, ((sat, start, stop, step, args['--frame'], args['--interp']) for sat in sats))
