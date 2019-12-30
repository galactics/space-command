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
    AnomalyListener,
)

from .station import StationDb
from .sat import Sat
from .utils import parse_date, parse_timedelta, docopt


def space_events(*argv):
    """Compute events for a given satellite

    Usage:
        space-events (- | <sat>...) [options]

    Options:
        <sat>                  Name of the satellite
        -d, --date <date>      Starting date of the computation [default: now]
        -r, --range <range>    Range of the computation [default: 6h]
        -s, --step <step>      Step of the conmputation [default: 3m] 
        -e, --events <events>  Selected events, space separated [default: all]

    Available events:
        station=<station>  Display AOS, LOS and max elevation events for a station
        station            Same but for all stations
        light              Display umbra and penumbra events
        node               Display ascending and descending nodes events
        apside             Display periapsis and apoapsis events
        terminator         Display terminator crossing event
        aol=<aol>          Display crossing of an Argument of Latitude (in deg)
        all                Display all non-specific events (station, light, node
                           apside, and terminator)
    Example:
        space events ISS --events "aol=90 apside node"
    """

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
                if "station=" in args["--events"]:
                    for x in args["--events"].split():
                        if x.strip().startswith("station="):
                            name = x.partition("station=")[2].strip()
                            listeners.extend(stations_listeners(StationDb.get(name)))
                else:
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
            if "aol" in args["--events"]:
                for x in args["--events"].split():
                    if x.strip().startswith("aol="):
                        v = float(x.partition("aol=")[2])
                        listeners.append(AnomalyListener(np.radians(v), anomaly="aol"))

            for orb in sat.orb.iter(
                start=start, stop=stop, step=step, listeners=listeners
            ):

                if orb.event is None:
                    continue

                if isinstance(orb.event, (MaxEvent, SignalEvent)):
                    if isinstance(orb.event, SignalEvent) and orb.event.elev == 0:
                        # Discard comments for null elevation
                        comment = ""
                    else:
                        orb2 = orb.copy(frame=orb.event.station, form="spherical")
                        comment = "{:0.2f} deg".format(np.degrees(orb2.phi))
                else:
                    comment = ""

                print(
                    "{:%Y-%m-%dT%H:%M:%S.%f}  {}  {}".format(
                        orb.date, orb.event, comment
                    )
                )

            print()
    except KeyboardInterrupt:
        print("\r    ")
        print("Interrupted")
