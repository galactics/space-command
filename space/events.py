import sys
import numpy as np
from beyond.orbits.listeners import (
    NodeListener,
    ApsideListener,
    LightListener,
    stations_listeners,
    SignalEvent,
    MaxEvent,
    TerminatorListener,
)

from .clock import Date, timedelta
from .station import StationDb
from .sat import Sat
from .utils import parse_date, parse_timedelta


def space_events(*argv):
    """Compute events for a given satellite

    Usage:
        space-events (- | <sat>...) [options]

    Options:
        <sat>                  Name of the satellite
        -d, --date <date>      Starting date of the computation [default: now]
        -r, --range <range>    Range of the computation [default: 1d]
        -s, --step <step>      Step of the conmputation [default: 3m] 
        -e, --events <events>  Selected events [default: all]

    Available events are: 'station', 'light', 'node', 'apside', 'terminator', and
    'all'
    """

    from .utils import docopt

    args = docopt(space_events.__doc__, argv=argv)

    try:
        satlist = Sat.from_input(
            *args["<sat>"], text=sys.stdin.read() if args["-"] else ""
        )
        start = parse_date(args["--date"])
        stop = parse_timedelta(args["--range"])
        step = parse_timedelta(args["--step"])
    except ValueError as e:
        print(e, file=sys.stdout)
        sys.exit(1)

    try:
        for sat in satlist:
            print(sat.name)
            print("=" * len(sat.name))
            listeners = []

            if "station" in args["--events"] or args["--events"] == "all":
                for sta in StationDb.list().values():
                    listeners.extend(stations_listeners(sta))

            if "light" in args["--events"] or args["--events"] == "all":
                listeners.append(LightListener())
                listeners.append(LightListener("penumbra"))
            if "node" in args["--events"] or args["--events"] == "all":
                listeners.append(NodeListener())
            if "apside" in args["--events"] or args["--events"] == "all":
                listeners.append(ApsideListener())
            if "terminator" in args["--events"] or args["--events"] == "all":
                listeners.append(TerminatorListener())

            for orb in sat.orb.iter(
                start=start, stop=stop, step=step, listeners=listeners
            ):

                if orb.event is None:
                    continue

                if isinstance(orb.event, (MaxEvent, SignalEvent)):
                    orb2 = orb.copy(frame=orb.event.station, form="spherical")
                    other = "{:0.2f}".format(np.degrees(orb2.phi))
                else:
                    other = ""

                print(
                    "{:20} {:%Y-%m-%dT%H:%M:%S.%f} {}".format(
                        orb.event if orb.event is not None else "", orb.date, other
                    )
                )

            print()
    except KeyboardInterrupt:
        print("\r    ")
        print("Interrupted")
