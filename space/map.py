import numpy as np
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button

from beyond.constants import Earth
from beyond.env.solarsystem import get_body

from .utils import circle
from .stations import StationDb
from .clock import Date, timedelta


class SatAnim:

    COLORS = 'r', 'g', 'b', 'c', 'm', 'y', 'k', 'w'

    def __init__(self, sats):
        self.sats = sats
        self.multiplier = None
        self.interval = 200

        mpl.rcParams['toolbar'] = 'None'

        path = Path(__file__).parent / "static/earth.png"
        im = plt.imread(str(path))
        self.fig = plt.figure(figsize=(15.2, 8.2))
        plt.imshow(im, extent=[-180, 180, -90, 90])
        plt.xlim([-180, 180])
        plt.ylim([-90, 90])
        plt.grid(True, linestyle=':', alpha=0.4)
        plt.xticks(range(-180, 181, 30))
        plt.yticks(range(-90, 91, 30))
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.1)

        self.sun, = plt.plot([], [], 'yo', markersize=10, markeredgewidth=0, animated=True, zorder=2)
        self.moon, = plt.plot([], [], 'wo', markersize=10, markeredgewidth=0, animated=True, zorder=2)
        self.night = plt.fill_between([], [], color='k', alpha=0.3, lw=0, animated=True, zorder=1)
        self.date_text = plt.text(-175, 80, "")

        for station in StationDb.list().values():
            lat, lon = np.degrees(station.latlonalt[:-1])
            plt.plot([lon], [lat], 'k+')
            plt.text(lon + 1, lat + 1, station.abbr)

        # For each satellite, initialisation of graphical representation
        for i, sat in enumerate(self.sats):
            color = self.COLORS[i % len(self.COLORS)]

            sat.point, = plt.plot([], [], 'o', ms=5, color=color, animated=True, zorder=10)
            sat.circle, = plt.plot([], [], '.', ms=2, color=color, animated=True, zorder=10)
            sat.text = plt.text(0, 0, sat.name, color=color, animated=True, zorder=10)

        self.bslow = Button(plt.axes([0.05, 0.02, 0.04, 0.05]), 'Slower')
        self.bslow.on_clicked(self.slower)
        self.breal = Button(plt.axes([0.10, 0.02, 0.08, 0.05]), 'Real Time')
        self.breal.on_clicked(self.real)
        self.bplay = Button(plt.axes([0.19, 0.02, 0.04, 0.05]), 'x1')
        self.bplay.on_clicked(self.reset)
        self.bfast = Button(plt.axes([0.24, 0.02, 0.04, 0.05]), 'Faster')
        self.bfast.on_clicked(self.faster)

        self.ani = FuncAnimation(self.fig, self, interval=self.interval, blit=True)

    def __call__(self, frame):

        plot_list = []

        date = self.date()

        if self.multiplier is None:
            text = "real time"
        elif self.multiplier >= 1:
            text = "x%d" % (self.multiplier)
        elif self.multiplier > 0:
            text = "x 1/%d" % (1 / self.multiplier)
        elif self.multiplier <= -1:
            text = "x {}".format(self.multiplier)
        else:
            text = "x -1/%d" % (-1 / self.multiplier)

        self.date_text.set_text("{:%Y-%m-%d %H:%M:%S}\n{}".format(
            date,
            text
        ))
        plot_list.append(self.date_text)

        for sat in self.sats:
            # Updating position of the satellite
            orb = sat.orb.propagate(date)
            lon, lat = self.lonlat(orb)
            sat.point.set_data([lon], [lat])
            plot_list.append(sat.point)

            # Updating the label
            sat.text.set_position((lon + 0.75, lat + 0.75))
            plot_list.append(sat.text)

            # Updating the circle of visibility
            lonlat = np.degrees(circle(*orb[:3]))
            lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180
            sat.circle.set_data(lonlat[:, 0], lonlat[:, 1])
            plot_list.append(sat.circle)

        # Updating the sun
        sun = get_body('Sun').propagate(date)
        lon, lat = self.lonlat(sun)
        self.sun.set_data([lon], [lat])
        plot_list.append(self.sun)

        # Updating the night
        lonlat = np.degrees(circle(*sun[:3]))
        lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180
        season = -95 if lat > 0 else 95
        lonlat = lonlat[lonlat[:, 0].argsort()]  # Sorting array by ascending longitude

        lonlat = np.concatenate([
            [
                [-185, season],
                [-185, lonlat[0, 1]]
            ],
            lonlat,
            [
                [185, lonlat[-1, 1]],
                [185, season],
            ]
        ])

        verts = [lonlat]

        # Eclipse (part of the orbit when the satellite is not illuminated by
        # the sun)
        if len(self.sats) == 1:
            virt_alt = Earth.r * orb.r / np.sqrt(orb.r ** 2 - Earth.r ** 2)
            theta = sun.theta + np.pi
            phi = -sun.phi
            lonlat = np.degrees(circle(virt_alt, theta, phi))
            lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180
            # print(lonlat[:, 0])

            if all(-175 < lonlat[:, 0]) and all(lonlat[:, 0] < 175):
                verts.append(lonlat)
            else:
                pos_lonlat = lonlat.copy()
                neg_lonlat = lonlat.copy()

                pos_lonlat[pos_lonlat[:, 0] < 0, 0] += 360
                neg_lonlat[neg_lonlat[:, 0] > 0, 0] -= 360

                verts.extend([pos_lonlat, neg_lonlat])

        self.night.set_verts(verts)
        plot_list.insert(0, self.night)

        # Updating the moon
        moon = get_body('Moon').propagate(date)
        lon, lat = self.lonlat(moon)
        self.moon.set_data([lon], [lat])
        plot_list.append(self.moon)

        return plot_list

    @classmethod
    def lonlat(cls, orb):
        orb.form = "spherical"
        orb.frame = "ITRF"
        lon, lat = np.degrees(orb[1:3])
        lon = ((lon + 180) % 360) - 180
        return lon, lat

    def date(self):
        if self.multiplier is None:
            self._date = Date.now()
        else:
            self._date += self.increment

        return self._date

    @property
    def increment(self):
        return timedelta(seconds=self.multiplier * self.interval / 1000)

    def real(self, *args, **kwargs):
        self.multiplier = None

    def reset(self, *args, **kwargs):
        self.multiplier = 1

    def faster(self, *args, **kwargs):
        if self.multiplier is None:
            self.multiplier = 2.
        elif -1 / 8 <= self.multiplier < 0:
            self.multiplier = 1
        elif self.multiplier > 0:
            self.multiplier *= 2.
        else:
            self.multiplier /= 2.

    def slower(self, *args, **kwargs):
        if self.multiplier is None:
            self.multiplier = 1 / 2.
        elif 0 < self.multiplier <= 1 / 8:
            self.multiplier = -1
        elif self.multiplier > 0:
            self.multiplier /= 2.
        else:
            self.multiplier *= 2.


def space_map(*argv):
    """Animated map of earth with ground track of satellites

    Usage:
      space-map (- | <satellite>...)

    Option:
      <satellite>   Name of the satellites you want to display.
      -             If used, the orbit should be provided as stdin in TLE or
                    CCSDS format
    """

    from .utils import docopt
    from .passes import get_sats

    args = docopt(space_map.__doc__)
    sats = get_sats(*args['<satellite>'], stdin=args['-'])

    sat_anim = SatAnim(sats)

    plt.show()
