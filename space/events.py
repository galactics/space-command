import numpy as np
from beyond.orbits.listeners import (
    NodeListener, ApsideListener, LightListener, stations_listeners,
    SignalEvent, MaxEvent, TerminatorListener
)

from .clock import Date, timedelta
from .stations import StationDb
from .passes import get_sats


def space_events(*argv):
    """Compute events for a given satellite

    Usage:
        space-events (- | <sat>...) [--date <date>] [--events] [--range <range>]

    Options:
        <sat>                Name of the satellite
        -d, --date <date>    Starting date of the computation
        -r, --range <range>  Range of the computation, in days [default: 1]
        -e, --events         Only display events [default: False]
    """

    from .utils import docopt

    args = docopt(space_events.__doc__, argv=argv)

    satlist = get_sats(*args['<sat>'], stdin=args['-'])

    if not args['--date']:
        now = Date.now()
        start = Date(now.d, now.s // 3600 * 3600)
    else:
        start = Date.strptime(args['--date'], "%Y-%m-%dT%H:%M:%S")

    stop = timedelta(days=float(args['--range']))
    step = timedelta(minutes=3)

    try:
        for sat in satlist:
            print(sat.name)
            print("=" * len(sat.name))
            listeners = []

            for sta in StationDb.list().values():
                listeners.extend(stations_listeners(sta))

            listeners.append(LightListener())
            listeners.append(LightListener("penumbra"))
            listeners.append(NodeListener())
            listeners.append(ApsideListener())
            listeners.append(TerminatorListener())

            for orb in sat.orb.iter(start=start, stop=stop, step=step, listeners=listeners):

                if args['--events'] and orb.event is None:
                    continue

                if isinstance(orb.event, (MaxEvent, SignalEvent)):
                    orb2 = orb.copy(frame=orb.event.station, form="spherical")
                    other = "{:0.2f}".format(np.degrees(orb2.phi))
                else:
                    other = ""

                print("{:20} {:%Y-%m-%dT%H:%M:%S.%f} {}".format(
                    orb.event if orb.event is not None else "",
                    orb.date, other
                ))

            print()
    except KeyboardInterrupt:
        print("\r    ")
        print("Interrupted")
