#!/usr/bin/env python
# coding=utf-8

import numpy as np
import matplotlib.pyplot as plt

from docopt import docopt
from textwrap import dedent
from datetime import timedelta
from pathlib import Path

from beyond.utils import Date
from beyond.orbits.listeners import LightListener

from .satellites import Satellite
from .circle import circle
from .stations import get_station
from .tle import Tle


def space_passes(*argv):
    """\
    Compute and plot passes geometry

    Usage:
      space-passes <station> [<satellite>] [-d <date>] [-s <sec>] [-p <nb>]
      space-passes <station> [<satellite>] [-negf <f>]

    Option:
      -h --help          Show this help
      <station>          Location from which the satellite is tracked
      <satellite>        Satellite
      -d, --date <date>  Starting date of the simulation. Default is now
                         format: "%Y-%m-%dT%H:%M:%S")
      -n, --no-events    Don't compute AOS, MAX and LOS
      -e, --events-only  Only show AOS, MAX and LOS
      -s, --step <sec>   Step-size (in seconds) [default: 30]
      -p, --passes <nb>  Number of passes to display [default: 1]
      -g, --graphs       Display graphics with matplotlib
    """

    import sys

    args = docopt(dedent(space_passes.__doc__), argv=argv)

    if args['--date'] is None:
        now = Date.now()
        start = Date(now.d, round(now.s))
    else:
        start = Date.strptime(args['<date>'], "%Y-%m-%dT%H:%M:%S")

    step = timedelta(seconds=float(args['--step']))
    stop = timedelta(days=1)

    pass_nb = int(args['--passes'])
    events = True if not args['--no-events'] else False

    try:
        station = get_station(args["<station>"])
    except ValueError:
        print("Unknwon station '{}'".format(args['<station>']))
        sys.exit(-1)

    if args['<satellite>'] is not None:
        try:
            sats = [Satellite.get(name=args['<satellite>'])]
        except ValueError:
            print("Unknwon satellite '{}'".format(args['<satellite>']))
            sys.exit(-1)
    elif not sys.stdin.isatty():
        # Retrieve orbit from stdin (as a list of TLE)
        sats = []
        tles = Tle.from_string(sys.stdin.read())
        for tle in tles:
            sats.append(Satellite(
                name=tle.name,
                cospar_id=tle.cospar_id,
                norad_id=tle.norad_id
            ))
    else:
        print("No satellite defined")
        sys.exit(-1)

    lats, lons = [], []
    azims, elevs = [], []

    header = "Infos      Time                        Azim    Elev    Dist (km)  Light   "
    print(header)
    print("=" * len(header))

    light = LightListener()

    for sat in sats:
        count = 0
        for orb in station.visibility(sat.tle(), start=start, stop=stop, step=step, events=events):

            if args['--events-only'] and orb.info[:3] not in ('AOS', 'MAX', 'LOS'):
                continue

            azim = -np.degrees(orb.theta) % 360
            elev = np.degrees(orb.phi)
            azims.append(azim)
            elevs.append(90 - elev)
            r = orb.r / 1000.

            print("{orb.info:10} {sat.name}  {orb.date:%Y-%m-%dT%H:%M:%S.%f} {azim:7.2f} {elev:7.2f} {r:10.2f}  {light}".format(
                orb=orb, r=r, azim=azim, elev=elev, light=light.info(orb),
                sat=sat
            ))

            orb_itrf = orb.copy(frame='ITRF')
            lon, lat = np.degrees(orb_itrf[1:3])
            lats.append(lat)
            lons.append(lon)

            if orb.info.startswith("LOS"):
                print()
                count += 1
                if count == pass_nb:
                    break

    if args['--graphs']:
        path = Path(__file__).parent

        im = plt.imread("%s/static/earth.png" % path)

        plt.figure()
        ax = plt.subplot(111, projection='polar')
        ax.set_theta_zero_location('N')
        plt.plot(np.radians(azims), elevs, '.')
        ax.set_yticks(range(0, 90, 20))
        ax.set_yticklabels(map(str, range(90, 0, -20)))
        ax.set_rmax(90)

        plt.figure(figsize=(15.2, 8.2))
        plt.imshow(im, extent=[-180, 180, -90, 90])
        plt.plot(lons, lats, 'r.')

        lonlat = np.degrees(circle(*orb.copy(frame=station)[:3]))
        lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180

        plt.plot(lonlat[:, 0], lonlat[:, 1], 'g:')

        # Ground Station
        lat, lon = np.degrees(station.latlonalt[:-1])
        plt.plot([lon], [lat], 'bo')
        plt.text(lon + 1, lat + 1, station.abbr, color='blue')
        lon, lat = np.degrees(list(zip(*circle(orb_itrf.r, np.radians(lon), np.radians(lat)))))
        lon = ((lon + 180) % 360) - 180
        plt.plot(lon, lat, 'b', lw=2)

        plt.xlim([-180, 180])
        plt.ylim([-90, 90])
        plt.grid(linestyle=':')
        plt.xticks(range(-180, 181, 30))
        plt.yticks(range(-90, 91, 30))
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

        plt.show()
