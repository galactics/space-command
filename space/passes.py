#!/usr/bin/env python
# coding=utf-8

import sys
import numpy as np
import matplotlib.pyplot as plt

from docopt import docopt
from textwrap import dedent, indent
from pathlib import Path

from beyond.dates import Date, timedelta
from beyond.orbits.listeners import LightListener

from .tle import TleDatabase, TleNotFound
from .utils import circle
from .stations import StationDatabase
from .satellites import Satellite


def get_sats(*args, stdin=False):

    if len(args) > 0:
        try:
            sats = [TleDatabase.get(name=sat) for sat in args]
        except TleNotFound:
            print("Unknwon satellite '{}'".format(" ".join(args)))
            sys.exit(-1)
    elif stdin and not sys.stdin.isatty():
        stdin = sys.stdin.read()
        sats = Satellite.parse(stdin)

        if not sats:
            print("No orbit provided, data in stdin was:\n")
            print(indent(stdin, "   "))
            sys.exit(-1)
    else:
        print("No satellite provided")
        sys.exit(-1)

    return sats


def space_passes(*argv):
    """Compute and plot passes geometry

    Usage:
      space-passes <station> (- | <satellite>...) [options]

    Option:
      -h --help          Show this help
      <station>          Location from which the satellite is tracked
      <satellite>        Satellite to track.
      -                  If used the orbit should be provided as stdin in TLE
                         or CCSDS format (see example)
      -d, --date <date>  Starting date of the simulation. Default is now
                         (format: "%Y-%m-%dT%H:%M:%S")
      -n, --no-events    Don't compute AOS, MAX and LOS
      -e, --events-only  Only show AOS, MAX and LOS
      -s, --step <sec>   Step-size (in seconds) [default: 30]
      -p, --passes <nb>  Number of passes to display [default: 1]
      -g, --graphs       Display graphics with matplotlib

    Examples:
      Simple computation of the ISS, TLS is the name of my station

          $ space passes TLS ISS

      Hubble is not part of my satellite database, but I want to compute its
      visibility just once

          $ space tle norad 20580 | space passes TLS

    """

    args = docopt(dedent("    " + space_passes.__doc__), argv=argv)

    if args['--date'] is None:
        now = Date.now()
        start = Date(now.d, round(now.s))
    else:
        start = Date.strptime(args['--date'], "%Y-%m-%dT%H:%M:%S")

    step = timedelta(seconds=float(args['--step']))
    stop = timedelta(days=1)

    pass_nb = int(args['--passes'])
    events = True if not args['--no-events'] else False

    try:
        station = StationDatabase.get(args["<station>"])
    except ValueError:
        print("Unknwon station '{}'".format(args['<station>']))
        sys.exit(-1)

    sats = get_sats(*args['<satellite>'], stdin=args["-"])

    lats, lons = [], []
    azims, elevs = [], []

    light = LightListener()

    # Computation of the passes
    for sat in sats:
        header = "Infos     Sat%s  Time                 Azim    Elev    Dist (km)  Light    " % (" " * (len(sat.name) - 3))
        print(header)
        print("=" * len(header))
        count = 0
        for orb in station.visibility(sat.orb, start=start, stop=stop, step=step, events=events):

            if args['--events-only'] and (orb.event is None or orb.event.info not in ('AOS', 'MAX', 'LOS')):
                continue

            azim = -np.degrees(orb.theta) % 360
            elev = np.degrees(orb.phi)
            azims.append(azim)
            elevs.append(90 - elev)
            r = orb.r / 1000.

            print("{event:9} {sat.name}  {orb.date:%Y-%m-%dT%H:%M:%S} {azim:7.2f} {elev:7.2f} {r:10.2f}  {light}".format(
                orb=orb, r=r, azim=azim, elev=elev, light=light.info(orb),
                sat=sat, event=orb.event if orb.event is not None else ""
            ))

            orb_itrf = orb.copy(frame='ITRF')
            lon, lat = np.degrees(orb_itrf[1:3])
            lats.append(lat)
            lons.append(lon)

            if orb.event is not None and orb.event.info == "LOS":
                print()
                count += 1
                if count == pass_nb:
                    break

    # Plotting
    if args['--graphs']:
        path = Path(__file__).parent

        im = plt.imread("%s/static/earth.png" % path)

        # Polar plot of the passes
        plt.figure()
        ax = plt.subplot(111, projection='polar')
        ax.set_theta_zero_location('N')
        plt.plot(np.radians(azims), elevs, '.')
        ax.set_yticks(range(0, 90, 20))
        ax.set_yticklabels(map(str, range(90, 0, -20)))
        ax.set_rmax(90)

        # Ground-track of the passes
        plt.figure(figsize=(15.2, 8.2))
        plt.imshow(im, extent=[-180, 180, -90, 90])
        plt.plot(lons, lats, 'r.')

        color = "#202020"

        # Ground Station
        lat, lon = np.degrees(station.latlonalt[:-1])
        plt.plot([lon], [lat], 'o', color=color)
        plt.text(lon + 1, lat + 1, station.abbr, color=color)
        lon, lat = np.degrees(list(zip(*circle(orb_itrf.r, np.radians(lon), np.radians(lat)))))
        lon = ((lon + 180) % 360) - 180
        plt.plot(lon, lat, '.', color=color, ms=2)

        plt.xlim([-180, 180])
        plt.ylim([-90, 90])
        plt.grid(linestyle=':')
        plt.xticks(range(-180, 181, 30))
        plt.yticks(range(-90, 91, 30))
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

        plt.show()
