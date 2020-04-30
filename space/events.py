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
    RadialVelocityListener,
    events_iterator,
)

from .station import StationDb
from .sat import Sat
from .utils import parse_date, parse_timedelta, docopt


def complete_iterator(satlist, start, stop, step, listeners):
    """Iterate over satellite list and date range

    Its only use is to be fed to sorted() when this is requested
    """
    for sat in satlist:
        iterator = sat.orb.iter(start=start, stop=stop, step=step, listeners=listeners)
        for orb in events_iterator(iterator):
            yield sat, orb


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
        --csv                  Data in CSV
        --sep <sep>            Separator [default: ,]
        --sort                 If multiple satellites are provided, sort all results by date

    Available events:
        station=<station>  Display AOS, LOS and max elevation events for a station
        station            Same but for all stations
        light              Display umbra and penumbra events
        node               Display ascending and descending nodes events
        apside             Display periapsis and apoapsis events
        terminator         Display terminator crossing event
        aol=<aol>          Display crossing of an Argument of Latitude (in deg)
        radial=<station>   Display radial velocity crossing event
        all                Display all non-specific events (station, light, node
                           apside, and terminator)
    Example:
        space events ISS --events "aol=90 apside node"
    """

    args = docopt(space_events.__doc__, argv=argv)

    try:
        satlist = Sat.from_command(
            *args["<sat>"], text=sys.stdin.read() if args["-"] else ""
        )
        start = parse_date(args["--date"])
        stop = parse_timedelta(args["--range"])
        step = parse_timedelta(args["--step"])
    except ValueError as e:
        print(e, file=sys.stdout)
        sys.exit(1)

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
    for x in args["--events"].split():
        if x.strip().startswith("radial="):
            name = x.partition("radial=")[2].strip()
            listeners.append(
                RadialVelocityListener(StationDb.get(name), sight=True)
            )
        elif x.strip().startswith("aol="):
            v = float(x.partition("aol=")[2])
            listeners.append(AnomalyListener(np.radians(v), anomaly="aol"))

    try:
        if args["--sort"]:
            iterator = sorted(complete_iterator(satlist, start, stop, step, listeners), key=lambda x: x[1].date)
        else:
            iterator = complete_iterator(satlist, start, stop, step, listeners)

        for sat, orb in iterator:

            if isinstance(orb.event, (MaxEvent, SignalEvent)):
                if isinstance(orb.event, SignalEvent) and orb.event.elev == 0:
                    # Discard comments for null elevation
                    comment = ""
                else:
                    orb2 = orb.copy(frame=orb.event.station, form="spherical")
                    comment = "{:0.2f} deg".format(np.degrees(orb2.phi))
            else:
                comment = ""

            if args["--csv"]:
                sep = args["--sep"]
                print_str = f"{orb.date:%Y-%m-%dT%H:%M:%S.%f}{sep}{sat.name}{sep}{getattr(orb.event, 'station', '')}{sep}{orb.event}{sep}{comment}"
            else:
                print_str = f"{orb.date:%Y-%m-%dT%H:%M:%S.%f}  {sat.name}  {orb.event}  {comment}"

            print(print_str)

    except KeyboardInterrupt:
        print("\r    ")
        print("Interrupted")
