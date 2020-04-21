import sys
import logging
import matplotlib.pyplot as plt

from ..utils import docopt, parse_date
from ..sat import Sat

from .map import MapAnim

log = logging.getLogger(__name__)


def space_map(*argv):
    """Animated map of earth with ground track of satellites

    Usage:
        space-map (- | <satellite>...) [options]

    Option:
        <satellite>        Name of the satellites you want to display.
        -                  If used, the orbit should be provided as stdin in
                           TLE or CCSDS format
        -d, --date <date>  Date from which to start the animation [default: now]
        --no-ground-track  Hide ground-track by default
        --no-circle        hide circle of visibility by default
    """

    args = docopt(space_map.__doc__)
    try:
        sats = list(
            Sat.from_command(
                *args["<satellite>"], text=sys.stdin.read() if args["-"] else ""
            )
        )
    except ValueError as e:
        log.error(e)
        sys.exit(1)

    sat_anim = MapAnim(
        sats,
        parse_date(args["--date"]),
        groundtrack=not args["--no-ground-track"],
        circle=not args["--no-circle"],
    )

    plt.show()
