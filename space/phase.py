import numpy as np

import logging
from pathlib import Path
import matplotlib.pyplot as plt

from beyond.env import jpl
from beyond.env import solarsystem as solar

log = logging.getLogger(__name__)


def compute_phase(first, second, center):
    first = first.copy(form="spherical", frame=center)
    second = second.copy(form="spherical", frame=center)

    # Phase computation is just the difference between the right ascension
    return second.theta - first.theta


def illumination(phase):
    return (1 - np.cos(phase)) / 2


def draw_umbra(phase_norm):

    radius = 138
    y = np.linspace(-radius, radius, 100)
    x = np.sqrt(radius ** 2 - y ** 2)
    r = 2 * x

    if phase_norm < 0.5:
        left = 2 * phase_norm * r - r + x
        right = x
    else:
        left = -x
        right = 2 * phase_norm * r - r - x

    return np.concatenate([left, right]), np.concatenate([y, y[::-1]])


def draw_phase(date, phase, body="Moon", filepath=False):

    path = Path(__file__).parent

    fig = plt.figure()
    ax = plt.subplot(111)

    phase_norm = (phase % (2 * np.pi)) / (2 * np.pi)
    x, y = draw_umbra(phase_norm)

    img_path = (path / "static" / body.lower()).with_suffix(".png")
    if img_path.exists():
        im = plt.imread(str(img_path))
        img = plt.imshow(im, extent=[-150, 150, -150, 150])
    else:
        # im = plt.imread(str(path / "static/moon.png"))
        circle = plt.Circle((0, 0), 138, color="orange")
        ax.add_artist(circle)
        ax.set_aspect("equal")

    plt.fill_between(x, y, color="k", lw=0, alpha=0.8, zorder=100)

    plt.xlim([-150, 150])
    plt.ylim([-150, 150])
    plt.axis("off")

    x_text = -140

    date_txt = "{} - {:%d/%m %H:%M:%S} - {:.1f}%".format(
        body, date, illumination(phase) * 100
    )
    plt.text(x_text, 140, date_txt, color="white")

    plt.tight_layout()

    if filepath:
        plt.savefig(filepath, bbox_inches="tight")
        log.info("file saved at {}".format(Path(filepath).absolute()))
    else:
        plt.show()

    plt.close()


def space_phase(*argv):
    """Compute the phase of the moon or other solar system bodies

    Usage:
        space-phase <body> [<date>] [--graph] [--frame <frame>] [-a] [--file <file>]

    Options:
        <body>            Body
        <date>            Date to compute the moon phase at [default: now]
                          (format %Y-%m-%dT%H:%M:%S)
        -g, --graph       Display the moon phase
        -a, --analytical  Use analytical model instead of JPL files
        --file <file>     File
    """
    import sys
    from .utils import docopt, parse_date
    from .station import StationDb

    args = docopt(space_phase.__doc__)

    if args["<date>"] is None:
        args["<date>"] = "now"

    try:
        date = parse_date(args["<date>"])
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    StationDb.list()

    body = args["<body>"]

    if body == "Moon":
        center = "EME2000"
        second = "Sun"
    else:
        center = body
        body = "Sun"
        second = "Earth"

    if args["--analytical"] and body.lower() == "moon":
        first = solar.get_body(body).propagate(date)
        second = solar.get_body(second).propagate(first.date)
        src = "analytical"
    else:
        src = "JPL"
        if args["--analytical"]:
            log.warning(
                "No analytical model available for '{}'. Switching to JPL source".format(
                    body
                )
            )
        jpl.create_frames()
        first = jpl.get_orbit(body, date)
        second = jpl.get_orbit(second, first.date)

    if body == "Moon":
        phase = compute_phase(first, second, center)
    else:
        phase = np.pi - compute_phase(first, second, center)
        body = center

    illumin = illumination(phase)

    log.debug("Computing {} phase using source '{}'".format(body, src))
    log.info("{} at {:%Y-%m-%dT%H:%M:%S} : {:0.2f}%".format(body, date, illumin * 100))

    if args["--graph"] or args["--file"]:
        draw_phase(date, phase, body=args["<body>"], filepath=args["--file"])
