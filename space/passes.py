#!/usr/bin/env python
# coding=utf-8

import sys
import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path

from beyond.orbits.listeners import LightListener

from .clock import Date, timedelta
from .utils import circle, docopt
from .stations import StationDb
from .satellites import get_sats


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
      -d --date <date>   Starting date of the simulation. Default is now
                         (format: "%Y-%m-%dT%H:%M:%S")
      -r --range <days>  Range of the computation [default: 1]
      -n --no-events     Don't compute AOS, MAX and LOS
      -e --events-only   Only show AOS, MAX and LOS
      -l --light         Compute day/penumbra/umbra transitions
      -s --step <sec>    Step-size (in seconds) [default: 30]
      -p --passes <nb>   Number of passes to display [default: 1]
      -g --graphs        Display graphics with matplotlib
      -z --zenital       Reverse direction of azimut angle on the polar plot
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
        try:
            start = Date.strptime(args['--date'], "%Y-%m-%dT%H:%M:%S")
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(-1)

    try:
        step = timedelta(seconds=float(args['--step']))
        stop = timedelta(days=float(args['--range']))
        pass_nb = int(args['--passes'])
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(-1)

    try:
        station = StationDb.get(args["<station>"])
    except ValueError:
        print("Unknwon station '{}'".format(args['<station>']))
        sys.exit(-1)

    events = not args['--no-events']

    sats = get_sats(*args['<satellite>'], stdin=args["-"])

    light = LightListener()

    if args['--light'] and events:
        events = [light, LightListener(LightListener.PENUMBRA)]

    # Computation of the passes
    for sat in sats:

        lats, lons = [], []
        lats_e, lons_e = [], []
        azims, elevs = [], []
        azims_e, elevs_e, text_e = [], [], []

        header = "Infos        Sat%s  Time                       Azim    Elev    Dist (km)  Light    " % (" " * (len(sat.name) - 3))
        print(header)
        print("=" * len(header))
        count = 0
        for orb in station.visibility(sat.orb, start=start, stop=stop, step=step, events=events):

            if args['--events-only'] and orb.event is None:
                continue

            azim = -np.degrees(orb.theta) % 360
            elev = np.degrees(orb.phi)
            azims.append(azim)
            elevs.append(90 - elev)
            r = orb.r / 1000.

            if orb.event:
                azims_e.append(azim)
                elevs_e.append(90 - elev)

            light_info = "Umbra" if light(orb) <= 0 else "Light"

            print("{event:15} {sat.name}  {orb.date:%Y-%m-%dT%H:%M:%S.%f} {azim:7.2f} {elev:7.2f} {r:10.2f}  {light}".format(
                orb=orb, r=r, azim=azim, elev=elev, light=light_info,
                sat=sat, event=orb.event if orb.event is not None else ""
            ))

            orb_itrf = orb.copy(frame='ITRF')
            lon, lat = np.degrees(orb_itrf[1:3])
            lats.append(lat)
            lons.append(lon)

            if orb.event:
                lats_e.append(lat)
                lons_e.append(lon)
                text_e.append(orb.event.info)

            if orb.event is not None and orb.event.info == "LOS" and orb.event.elev == 0:
                print()
                count += 1
                if count == pass_nb:
                    break

        # Plotting
        if args['--graphs']:

            # Polar plot of the passes
            plt.figure(figsize=(15.2, 8.2))

            ax = plt.subplot(121, projection='polar')
            ax.set_theta_zero_location('N')

            plt.title("{} from {}".format(sat.name, station))
            if not args['--zenital']:
                ax.set_theta_direction(-1)

            plt.plot(np.radians(azims), elevs, '.')

            for azim, elev, txt in zip(azims_e, elevs_e, text_e):
                plt.plot(np.radians(azim), elev, 'ro')
                plt.text(np.radians(azim), elev, txt, color="r")

            if station.mask is not None:

                m_azims = np.arange(0, 2 * np.pi, np.pi / 180.)
                m_elevs = [90 - np.degrees(station.get_mask(azim)) for azim in m_azims]

                plt.plot(-m_azims, m_elevs)

            ax.set_yticks(range(0, 90, 20))
            ax.set_yticklabels(map(str, range(90, 0, -20)))
            ax.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
            ax.set_rmax(90)

            plt.tight_layout()

            plt.subplot(122)
            # Ground-track of the passes
            path = Path(__file__).parent
            im = plt.imread("%s/static/earth.png" % path)
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
            plt.tight_layout()
            plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    if args['--graphs']:
        plt.show()
