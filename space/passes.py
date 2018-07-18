#!/usr/bin/env python
# coding=utf-8

import sys
import numpy as np
import matplotlib.pyplot as plt

from textwrap import indent
from pathlib import Path

from beyond.dates import Date, timedelta
from beyond.orbits.listeners import LightListener

from .tle import TleDatabase, TleNotFound
from .utils import circle, docopt
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
      -z, --zenital      Reverse direction of azimut angle on the polar plot
                         to show as the passes as seen from the station
                         looking to the sky

    Examples:
      Simple computation of the ISS, TLS is the name of my station

          $ space passes TLS ISS

      Hubble is not part of my satellite database, but I want to compute its
      visibility just once

          $ space tle norad 20580 | space passes TLS

    """

    args = docopt(space_passes.__doc__)

    if args['--date'] is None:
        now = Date.now()
        start = Date(now.d, now.s - (now.s % 1440))
    else:
        start = Date.strptime(args['--date'], "%Y-%m-%dT%H:%M:%S")

    step = timedelta(seconds=float(args['--step']))
    stop = timedelta(days=1)

    pass_nb = int(args['--passes'])

    try:
        station = StationDatabase.get(args["<station>"])
    except ValueError:
        print("Unknwon station '{}'".format(args['<station>']))
        sys.exit(-1)

    events = not args['--no-events']

    sats = get_sats(*args['<satellite>'], stdin=args["-"])

    light = LightListener()

    # Computation of the passes
    for sat in sats:

        lats, lons = [], []
        lats_e, lons_e = [], []
        azims, elevs = [], []
        azims_e, elevs_e = [], []

        header = "Infos        Sat%s  Time                       Azim    Elev    Dist (km)  Light    " % (" " * (len(sat.name) - 3))
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

            if orb.event:
                azims_e.append(azim)
                elevs_e.append(90 - elev)

            print("{event:12} {sat.name}  {orb.delayed_date:%Y-%m-%dT%H:%M:%S.%f} {azim:7.2f} {elev:7.2f} {r:10.2f}  {light}".format(
                orb=orb, r=r, azim=azim, elev=elev, light=light.info(orb),
                sat=sat, event=orb.event if orb.event is not None else ""
            ))

            orb_itrf = orb.copy(frame='ITRF')
            lon, lat = np.degrees(orb_itrf[1:3])
            lats.append(lat)
            lons.append(lon)

            if orb.event:
                lats_e.append(lat)
                lons_e.append(lon)

            if orb.event is not None and orb.event.info == "LOS" and orb.event.elev == 0:
                print()
                count += 1
                if count == pass_nb:
                    break

        # Plotting
        if args['--graphs']:
            path = Path(__file__).parent

            im = plt.imread("%s/static/earth.png" % path)

            # Polar plot of the passes
            plt.figure(figsize=(15.2, 8.2))

            plt.suptitle(sat.name)

            ax = plt.subplot(121, projection='polar')
            ax.set_theta_zero_location('N')

            if not args['--zenital']:
                ax.set_theta_direction(-1)

            plt.plot(np.radians(azims), elevs, '.')
            plt.plot(np.radians(azims_e), elevs_e, 'ro')

            if station.mask is not None:

                m_azims = np.arange(0, 2 * np.pi, np.pi / 180.)
                m_elevs = [90 - np.degrees(station.get_mask(azim)) for azim in m_azims]

                plt.plot(-m_azims, m_elevs)

            ax.set_yticks(range(0, 90, 20))
            ax.set_yticklabels(map(str, range(90, 0, -20)))
            ax.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
            ax.set_rmax(90)
            plt.text(np.radians(azims[0]), elevs[0], "AOS", color="r")
            plt.text(np.radians(azims[-1]), elevs[-1], "LOS", color="r")

            plt.subplot(122)
            # Ground-track of the passes
            plt.imshow(im, extent=[-180, 180, -90, 90])
            plt.plot(lons, lats, 'b.')

            plt.plot(lons_e, lats_e, 'r.')

            color = "#202020"

            # Ground Station
            sta_lat, sta_lon = np.degrees(station.latlonalt[:-1])
            plt.plot([sta_lon], [sta_lat], 'o', color=color)
            plt.text(sta_lon + 1, sta_lat + 1, station.abbr, color=color)

            # Visibility circle
            lon, lat = np.degrees(list(zip(*circle(orb_itrf.r, np.radians(sta_lon), np.radians(sta_lat)))))
            lon = ((lon + 180) % 360) - 180
            plt.plot(lon, lat, '.', color=color, ms=2)

            # Mask
            if station.mask is not None:
                m_azims = np.arange(0, 2 * np.pi, np.pi / 180.)
                m_elevs = [station.get_mask(azim) for azim in m_azims]
                mask = [m_azims, m_elevs]

                lon, lat = np.degrees(list(zip(*circle(orb_itrf.r, np.radians(sta_lon), np.radians(sta_lat), mask=mask))))
                lon = ((lon + 180) % 360) - 180
                plt.plot(lon, lat, color='c', ms=2)

            plt.xlim([-180, 180])
            plt.ylim([-90, 90])
            plt.grid(linestyle=':')
            plt.xticks(range(-180, 181, 30))
            plt.yticks(range(-90, 91, 30))
            plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    if args['--graphs']:
        plt.show()
