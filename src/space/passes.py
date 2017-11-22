#!/usr/bin/env python
# coding=utf-8

import numpy as np
import matplotlib.pyplot as plt

from docopt import docopt
from textwrap import dedent, indent
from pathlib import Path

from beyond.dates import Date, timedelta
from beyond.orbits.listeners import LightListener

from .satellites import Satellite
from .circle import circle
from .stations import StationDatabase
from .tle import Tle


def space_passes(*argv):
    """\
    Compute and plot passes geometry

    Usage:
      space-passes <station> [<satellite>...] [options]

    Option:
      -h --help      Show this help
      <station>      Location from which the satellite is tracked
      <satellite>    Satellite to track. If absent the orbit of the satellite(s)
                     should be provided as stdin in TLE format (see example)
      --date <date>  Starting date of the simulation. Default is now
                     format: "%Y-%m-%dT%H:%M:%S")
      --no-events    Don't compute AOS, MAX and LOS
      --events-only  Only show AOS, MAX and LOS
      --step <sec>   Step-size (in seconds) [default: 30]
      --passes <nb>  Number of passes to display [default: 1]
      --graphs       Display graphics with matplotlib

    Examples:
      Simple computation of the ISS, TLS is the name of my station

          $ space passes TLS ISS

      Hubble is not part of my satellite database, but I want to compute its
      visibility just once

          $ space tle norad 20580 | space passes TLS

    """

    import sys

    ######################
    # Arguments handling #
    ######################
    args = docopt(dedent(space_passes.__doc__), argv=argv)

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

    if len(args['<satellite>']) > 0:
        try:
            sats = [Satellite.get(name=sat) for sat in args['<satellite>']]
        except ValueError:
            print("Unknwon satellite '{}'".format(args['<satellite>']))
            sys.exit(-1)
    elif not sys.stdin.isatty():
        # Retrieve orbit from stdin (as a list of TLE)

        stdin = sys.stdin.read()

        sats = [Satellite(
                name=tle.name,
                cospar_id=tle.cospar_id,
                norad_id=tle.norad_id) for tle in Tle.from_string(stdin)]

        if not sats:
            print("No TLE provided, data in stdin was:\n")
            print(indent(stdin, "   "))
            sys.exit(-1)
    else:
        print("No satellite defined")
        sys.exit(-1)

    ######################
    # Actual computation #
    ######################
    lats, lons = [], []
    azims, elevs = [], []

    header = "Infos    Sat  Time                 Azim    Elev    Dist (km)  Light    "
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

            print("{orb.info:8} {sat.name}  {orb.date:%Y-%m-%dT%H:%M:%S} {azim:7.2f} {elev:7.2f} {r:10.2f}  {light}".format(
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
