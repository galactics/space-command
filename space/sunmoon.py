import numpy as np

from pathlib import Path
import matplotlib.pyplot as plt

from beyond.dates import Date, timedelta
from beyond.env.solarsystem import get_body

from .utils import docopt
from .stations import StationDatabase


def compute_phase(orb):
    orb = orb.copy()
    sun = get_body('Sun')
    sun = sun.propagate(orb.date)

    sun.frame = orb.frame

    orb.form = 'spherical'
    sun.form = 'spherical'

    # Phase computation is just the difference between the right ascension
    return sun.theta - orb.theta


def illumination(phase):
    return (1 - np.cos(phase)) / 2


def draw_umbra(phase):

    radius = 138
    y = np.linspace(-radius, radius, 100)
    x = np.sqrt(radius ** 2 - y ** 2)
    r = 2 * x

    if phase < 0.5:
        left = 2 * phase * r - r + x
        right = x
    else:
        left = -x
        right = 2 * phase * r - r - x

    return np.concatenate([left, right]), np.concatenate([y, y[::-1]])


def draw_moon(date, station, phase, illumin, filepath=False):

    path = Path(__file__).parent

    plt.figure()

    x, y = draw_umbra(phase)

    im = plt.imread("%s/static/moon.png" % path)
    img = plt.imshow(im, extent=[-150, 150, -150, 150])
    plt.fill_between(x, y, color='k', lw=0, alpha=0.8)

    plt.xlim([-150, 150])
    plt.ylim([-150, 150])
    plt.axis('off')
    img.axes.get_xaxis().set_visible(False)
    img.axes.get_yaxis().set_visible(False)

    if station.latlonalt[0] < 0:
        # When in the south hemisphere, the view of the moon is reversed
        plt.gca().invert_xaxis()
        x_text = 140
    else:
        x_text = -140

    date_txt = "{:%d/%m %H:%M:%S} - {:.1f}%".format(date, illumin * 100)
    plt.text(x_text, 140, date_txt, color="white")

    if filepath:
        plt.savefig(filepath, bbox_inches='tight')
    else:
        plt.show()

    plt.close()


def print_visi(body, date, args):
    station = StationDatabase.get(name=args['<station>'])

    for orb in station.visibility(body.propagate(date), start=date, stop=timedelta(days=1.1), step=timedelta(minutes=60), events=True):
        if not orb.event:
            continue

        if orb.event.info.startswith("AOS") and orb.event.elev == 0:
            info = "%srise" % body.name
        elif orb.event.info.startswith("LOS") and orb.event.elev == 0:
            info = "%sset" % body.name
        elif orb.event.info == "MAX":
            info = "Max"
        else:
            continue

        print("{info:8} {orb.date:%Y-%m-%d %H:%M:%S} {azim:6.2f} {elev:6.2f}".format(
            orb=orb, azim=(360 - np.degrees(orb.theta)) % 360, info=info, elev=np.degrees(orb.phi)
        ))


def parse_date(arg):
    if arg is None:
        date = Date.now()
    else:
        date = Date.strptime(arg, "%Y-%m-%d")

    return date


def space_sun(*argv):
    """Compute sunrise and sunset dates from a station

    Usage:
        space-sun <station> [<date>]

    Options:
        <station>  Name of the station from which to compute
        <date>     Date for which to compute the sunrise and sunset
                   (YYYY-MM-DD)
    """

    args = docopt(space_sun.__doc__)

    date = parse_date(args['<date>'])

    sun = get_body('Sun')

    print_visi(sun, date, args)


def space_moon(*argv):
    """Compute the phase of the moon

    Usage:
        space-moon <station> [<date>] [--graph [--file <file>]]

    Options:
        <station>          Station from which the moon is observed
        <date>             Date for which to compute the moon phase (YYYY-MM-DD)
        -g, --graph        Display the moon phase
        -f, --file <file>  Save the drawing in a file
    """

    args = docopt(space_moon.__doc__)

    date = parse_date(args['<date>'])
    station = StationDatabase.get(name=args['<station>'])
    moon = get_body('Moon')

    moon_orb = moon.propagate(date)

    phase = compute_phase(moon_orb)
    phase_norm = (phase % (2 * np.pi)) / (2 * np.pi)
    illumin = illumination(phase)

    print("{:%Y-%m-%d}: {:6.2f}%".format(date, illumin * 100))

    print_visi(moon, date, args)

    if args['--graph']:
        draw_moon(date, station, phase_norm, illumin, filepath=args['--file'])
