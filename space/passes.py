#!/usr/bin/env python
# coding=utf-8

import sys
import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

from beyond.propagators.listeners import LightListener, RadialVelocityListener
from beyond.errors import UnknownFrameError
from beyond.env.solarsystem import get_body
from beyond.dates import timedelta

from .utils import circle, docopt, parse_date, parse_timedelta
from .station import StationDb
from .sat import Sat
from .map.background import set_background

log = logging.getLogger(__name__)


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
      -d --date <date>   Starting date of the computation [default: now]
                         (format: "%Y-%m-%dT%H:%M:%S")
      -r --range <days>  Range of the computation [default: 1d]
      -n --no-events     Don't compute AOS, MAX and LOS
      -e --events-only   Only show AOS, MAX and LOS
      -l --light         Compute day/penumbra/umbra transitions
      -s --step <step>   Step-size [default: 30s]
      -p --passes <nb>   Number of passes to display [default: 1]
      -g --graphs        Display graphics with matplotlib
      -z --zenital       Reverse direction of azimut angle on the polar plot
                         to show as the passes as seen from the station
                         looking to the sky
      --el --elevation   Plot elevation graphs
      --radial           Compute radial velocity nullation point
      --csv              Print in CSV format
      --sep=<sep>        CSV separator [default: ,]

    Examples:
      Simple computation of the ISS, TLS is the name of my station

          $ space passes TLS ISS

      Hubble is not part of my satellite database, but I want to compute its
      visibility just once

          $ space tle norad 20580 | space passes TLS

    """

    args = docopt(space_passes.__doc__)

    try:
        start = parse_date(args["--date"])
        step = parse_timedelta(args["--step"])
        stop = parse_timedelta(args["--range"])
        pass_nb = int(args["--passes"])
        sats = Sat.from_command(
            *args["<satellite>"], text=sys.stdin.read() if args["-"] else ""
        )
    except ValueError as e:
        log.error(e)
        sys.exit(1)

    try:
        station = StationDb.get(args["<station>"])
    except UnknownFrameError:
        log.error("Unknwon station '{}'".format(args["<station>"]))
        sys.exit(1)

    events = not args["--no-events"]

    light = LightListener()

    if args["--light"] and events:
        events = [light, LightListener(LightListener.PENUMBRA)]
    if args["--radial"]:
        rad = RadialVelocityListener(station, sight=True)
        if isinstance(events, list):
            events.append(rad)
        else:
            events = rad

    # Computation of the passes
    for i_sat, sat in enumerate(sats):

        lats, lons = [], []
        lats_e, lons_e = [], []
        azims, elevs = [], []
        azims_e, elevs_e, text_e = [], [], []

        info_size = 0
        if args["--csv"]:
            print(
                args["--sep"].join(
                    [
                        "date",
                        "event",
                        "name",
                        "azimut",
                        "elevation",
                        "distance",
                        "light",
                    ]
                )
            )
        else:
            info_size = len(station.name) + 10
            header = "Time                        Infos{} Sat{}     Azim    Elev  Dist (km)  Light    ".format(
                " " * (info_size - 5), " " * (len(sat.name) - 3)
            )

            print(header)
            print("=" * len(header))

        count = 0
        dates = []
        lights = []
        for orb in station.visibility(
            sat.orb, start=start, stop=stop, step=step, events=events
        ):

            if args["--events-only"] and orb.event is None:
                continue

            azim = -np.degrees(orb.theta) % 360
            elev = np.degrees(orb.phi)
            azims.append(azim)
            elevs.append(90 - elev)
            dates.append(orb.date)
            r = orb.r / 1000.0

            if orb.event:
                azims_e.append(azim)
                elevs_e.append(90 - elev)

            light_info = "Umbra" if light(orb) <= 0 else "Light"
            lights.append(light_info)

            if args["--csv"]:
                fmt = [
                    "{orb.date:%Y-%m-%dT%H:%M:%S.%f}",
                    "{event}",
                    "{sat.name}",
                    "{azim:.2f}",
                    "{elev:.2f}",
                    "{r:.2f}",
                    "{light}",
                ]
                fmt = args["--sep"].join(fmt)
            else:
                fmt = "{orb.date:%Y-%m-%dT%H:%M:%S.%f}  {event:{info_size}} {sat.name}  {azim:7.2f} {elev:7.2f} {r:10.2f}  {light}"

            print(
                fmt.format(
                    orb=orb,
                    r=r,
                    azim=azim,
                    elev=elev,
                    light=light_info,
                    sat=sat,
                    event=orb.event if orb.event is not None else "",
                    info_size=info_size,
                )
            )

            orb_itrf = orb.copy(frame="ITRF")
            lon, lat = np.degrees(orb_itrf[1:3])
            lats.append(lat)
            lons.append(lon)

            if orb.event:
                lats_e.append(lat)
                lons_e.append(lon)
                text_e.append(orb.event.info)

            if (
                orb.event is not None
                and orb.event.info == "LOS"
                and orb.event.elev == 0
            ):
                print()
                count += 1
                if count == pass_nb:
                    break

        # Plotting
        if args["--graphs"] and azims:

            # Polar plot of the passes
            plt.figure(f"{sat.name}", figsize=(15.2, 8.2))

            ax = plt.subplot(121, projection="polar")
            ax.set_theta_zero_location("N")

            plt.title("{} from {}".format(sat.name, station))
            if not args["--zenital"]:
                ax.set_theta_direction(-1)

            plt.plot(np.radians(azims), elevs, ".")

            for azim, elev, txt in zip(azims_e, elevs_e, text_e):
                plt.plot(np.radians(azim), elev, "ro")
                plt.text(np.radians(azim), elev, txt, color="r")

            if station.mask is not None:

                m_azims = np.arange(0, 2 * np.pi, np.pi / 180.0)
                m_elevs = [90 - np.degrees(station.get_mask(azim)) for azim in m_azims]

                plt.plot(-m_azims, m_elevs)

            # Add the Moon and Sun traces
            bodies = (("Sun", "yo", None), ("Moon", "wo", "k"))
            bodies_ephem = {}

            for body, marker, edge in bodies:

                b_ephem = get_body(body).propagate(orb.date).ephem(dates=dates)
                bodies_ephem[body] = b_ephem
                mazim, melev = [], []
                for m in station.visibility(b_ephem):
                    mazim.append(-m.theta)
                    melev.append(90 - np.degrees(m.phi))

                plt.plot(mazim, melev, marker, mec=edge, mew=0.5)

            ax.set_yticks(range(0, 90, 20))
            ax.set_yticklabels(map(str, range(90, 0, -20)))
            ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
            ax.set_rmax(90)

            plt.tight_layout()

            plt.subplot(122)
            # Ground-track of the passes
            set_background()
            plt.plot(lons, lats, "b.")

            plt.plot(lons_e, lats_e, "r.")

            color = "#202020"

            # Ground Station
            sta_lat, sta_lon = np.degrees(station.latlonalt[:-1])

            # Visibility circle
            lon, lat = np.degrees(
                list(zip(*circle(orb_itrf.r, *station.latlonalt[-2::-1])))
            )
            lon = ((lon + 180) % 360) - 180
            plt.plot(lon, lat, ".", color=color, ms=2)

            # Mask
            if station.mask is not None:
                m_azims = np.arange(0, 2 * np.pi, np.pi / 180.0)
                m_elevs = [station.get_mask(azim) for azim in m_azims]
                mask = [m_azims, m_elevs]

                lon, lat = np.degrees(
                    list(
                        zip(
                            *circle(
                                orb_itrf.r,
                                np.radians(sta_lon),
                                np.radians(sta_lat),
                                mask=mask,
                            )
                        )
                    )
                )
                lon = ((lon + 180) % 360) - 180
                plt.plot(lon, lat, color="c", ms=2)

            # Add the moon and sun traces
            for body, marker, edge in bodies:
                b_itrf = np.asarray(
                    bodies_ephem[body].copy(frame="ITRF", form="spherical")
                )
                lon = ((np.degrees(b_itrf[:, 1]) + 180) % 360) - 180
                lat = np.degrees(b_itrf[:, 2])
                plt.plot(lon, lat, marker, mec=edge, mew=0.5)

            plt.xlim([-180, 180])
            plt.ylim([-90, 90])
            plt.grid(linestyle=":")
            plt.xticks(range(-180, 181, 30))
            plt.yticks(range(-90, 91, 30))
            plt.tight_layout()
            plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

        if args["--elevation"]:

            plt.figure("Baleine", figsize=(12, 7))

            if "axb" not in locals():
                axb = None

            axb = plt.subplot(len(sats), 1, i_sat + 1, sharex=axb)

            plt.plot(dates, 90 - np.array(elevs), label="passes")
            light_curve = np.repeat(np.nan, len(dates))
            for i, l in enumerate(lights):
                if l == "Light":
                    light_curve[i] = 90 - elevs[i]

            plt.plot(dates, light_curve, "r", label="illuminated passes")

            ylim = plt.ylim()
            xlim = plt.xlim()
            sun_orb = get_body("Sun").propagate(start)
            sun_dates = [start]

            if sun_orb.copy(frame=station, form="spherical").phi > 0:
                sun = [0]
            else:
                sun = [91]

            for s in station.visibility(
                sun_orb, start=start, stop=stop, step=timedelta(minutes=20), events=True
            ):
                if not s.event or s.event.info not in ("AOS", "LOS"):
                    continue

                sun_dates.append(s.date)
                if s.event.info == "LOS":
                    sun.append(91)
                else:
                    sun.append(0)

            if (
                sun_orb.propagate(start + stop)
                .copy(frame=station, form="spherical")
                .phi
                > 0
            ):
                sun.append(0)
            else:
                sun.append(91)
            sun_dates.append(start + stop)

            plt.fill_between(
                sun_dates, sun, step="post", color="k", alpha=0.2, zorder=-100
            )

            plt.ylim(0, ylim[1])
            # plt.xlim(*xlim)
            plt.grid(ls=":")
            plt.ylabel(sat.name)

            if i_sat != len(sats) - 1:
                plt.xticks(color="w")

            axb.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

            plt.suptitle(station.name)
            plt.tight_layout()
            plt.subplots_adjust(hspace=0)

    if args["--graphs"] or args["--elevation"]:
        plt.show()
