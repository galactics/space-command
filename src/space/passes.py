#!/usr/bin/env python
# coding=utf-8

import numpy as np
import matplotlib.pyplot as plt

from docopt import docopt
from textwrap import dedent
from datetime import timedelta
from pathlib import Path

from beyond.utils import Date
from beyond.constants import c
from beyond.env.solarsystem import get_body
from beyond.orbits.listeners import LightListener

from .satellites import Satellite
from .circle import circle
from .stations import get_station


def space_passes(*argv):
    """\
    Compute and plot passes geometry

    Usage:
      space-passes <station> <sat> [<date>] [-p <nb>] [-g] [-f <f>]

    Option:
      -h --help        Show this help
      <station>        Location from which the satellite is tracked
      <sat>            Satellite
      <date>           Starting date of the simulation (format: "%Y-%m-%dT%H:%M:%S")
                       Default is now
      -p <nb>          Number of passes to display [default: 1]
      -g, --graphs     Display graphics with matplotlib
      -f, --freq <f>   Frequency in MHz used do compute doppler shift
    """

    args = docopt(dedent(space_passes.__doc__), argv=argv)

    if args['<date>'] is None:
        now = Date.now()
        start = Date(now.d, round(now.s))
    else:
        start = Date.strptime(args['<date>'], "%Y-%m-%dT%H:%M:%S")

    pass_nb = int(args['-p'])

    sat = Satellite.get(name=args['<sat>'])
    station = get_station(args["<station>"])

    count = 0
    lats, lons = [], []
    azims, elevs = [], []
    dops = []

    freq = args['--freq']

    if freq is None:
        print("        Time      Azim    Elev    Dist (km) RadVel(m/s) Light")
    else:
        freq = float(freq) * 1e6
        print("        Time      Azim    Elev    Dist (km) Doppler(Hz) Light")

    light = LightListener()

    print("==================================================================")
    for orb in station.visibility(sat.tle(), start=start, stop=timedelta(hours=24), step=timedelta(seconds=30), events=True):

        if orb.info.startswith("LOS"):
            sun = get_body('Sun').propagate(orb.date)

        azim = -np.degrees(orb.theta) % 360
        elev = np.degrees(orb.phi)
        azims.append(azim)
        elevs.append(90 - elev)
        r = orb.r / 1000.
        dop = orb.r_dot if freq is None else - orb.r_dot / c * freq
        if freq is not None:
            dops.append((orb.date.datetime, freq + dop))
        print("{orb.info:7} {orb.date:%H:%M:%S} {azim:7.2f} {elev:7.2f} {r:10.2f} {dop:10.2f}  {light}".format(
            orb=orb, r=r, azim=azim, elev=elev, dop=dop, light=light.info(orb),
        ))

        orb.frame = 'ITRF'
        lon, lat = np.degrees(orb[1:3])
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
        lat, lon = np.degrees(station.latlonalt[:-1])

        # Ground Station
        plt.plot([lon], [lat], 'bo')
        plt.text(lon + 1, lat + 1, station.abbr, color='blue')
        lon, lat = np.degrees(list(zip(*circle(orb.r, np.radians(lon), np.radians(lat)))))
        lon = ((lon + 180) % 360) - 180
        plt.plot(lon, lat, 'b', lw=2)

        # Sun
        sun.frame = 'ITRF'
        sun.form = 'spherical'
        sun_lon, sun_lat = np.degrees(sun[1:3])

        night = -90 if sun_lat > 0 else 90

        plt.plot([sun_lon], [sun_lat], 'o', color='#ffff00', markersize=10, markeredgewidth=0)
        lonlat = np.degrees(circle(*sun[:3]))
        lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180
        p = lonlat[:, 0].argsort()
        plt.fill_between(lonlat[p, 0], lonlat[p, 1], night, color='k', alpha=0.3, lw=0)

        earth = get_body('Earth')
        # earth_orbit = earth.propagate(now)
        # Eclipse
        virt_alt = earth.r * orb.r / np.sqrt(orb.r ** 2 - earth.r ** 2)
        theta = sun.theta + np.pi
        phi = -sun.phi
        lonlat = np.degrees(circle(virt_alt, theta, phi))

        lonlat[:, 0] = (lonlat[:, 0] + 180) % 360 - 180

        night = -90 if sun_lat > 0 else 90
        night = 0
        # if alpha + abs(sun.phi) < np.pi / 2:
        #     night = 0
        # else:
        #     night = -90 if sun_lat > 0 else 90
        #     p = lonlat[:, 1].argsort()
        #     lonlat = lonlat[p, :]

        eclipse = plt.fill_between(lonlat[:, 0], lonlat[:, 1], night, color='k', alpha=0.3, lw=0)

        plt.xlim([-180, 180])
        plt.ylim([-90, 90])
        plt.grid(linestyle=':')
        plt.xticks(range(-180, 181, 30))
        plt.yticks(range(-90, 91, 30))
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

        if freq is not None:
            plt.figure()
            dates, dops = zip(*dops)
            plt.plot(dates, dops)

        plt.show()
