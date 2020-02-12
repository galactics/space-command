import numpy as np
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button

from beyond.constants import Earth
from beyond.env.solarsystem import get_body

from ..utils import circle, orb2circle, orb2lonlat
from ..clock import Date, timedelta

from .wephem import WindowEphem
from .background import set_background


class MapAnim:

    COLORS = "r", "g", "b", "c", "m", "y", "k", "w"

    def __init__(self, sats, date, groundtrack=True, circle=True):
        self.sats = sats
        self.multiplier = None
        self.interval = 200
        self.circle = circle
        self.groundtrack = groundtrack

        if abs(date - Date.now()).total_seconds() > 1:
            self.date = date
            self.multiplier = 1

        mpl.rcParams["toolbar"] = "None"

        self.fig = plt.figure(figsize=(15.2, 8.2))
        self.ax = plt.subplot(111)
        set_background()
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.1)

        self.make_empty_plots()
        self.make_buttons()

        self.ani = FuncAnimation(self.fig, self, interval=self.interval, blit=True)

    def make_empty_plots(self):

        (self.sun,) = plt.plot(
            [], [], "yo", markersize=10, markeredgewidth=0, animated=True, zorder=2
        )
        (self.moon,) = plt.plot(
            [], [], "wo", markersize=10, markeredgewidth=0, animated=True, zorder=2
        )
        self.night = plt.fill_between(
            [], [], color="k", alpha=0.3, lw=0, animated=True, zorder=1
        )
        self.date_text = plt.text(-175, 80, "")

        # For each satellite, initialisation of graphical representation
        for i, sat in enumerate(self.sats):
            color = self.COLORS[i % len(self.COLORS)]

            (sat.point,) = plt.plot(
                [], [], "o", ms=5, color=color, animated=True, zorder=10
            )
            (sat.circle,) = plt.plot(
                [], [], ".", ms=2, color=color, animated=True, zorder=10
            )
            sat.text = plt.text(0, 0, sat.name, color=color, animated=True, zorder=10)
            sat.win_ephem = None if self.groundtrack else False

    def make_buttons(self):
        self.breverse = Button(plt.axes([0.02, 0.02, 0.04, 0.05]), "Reverse")
        self.breverse.on_clicked(self.reverse)
        self.bslow = Button(plt.axes([0.07, 0.02, 0.04, 0.05]), "Slower")
        self.bslow.on_clicked(self.slower)
        self.breal = Button(plt.axes([0.12, 0.02, 0.08, 0.05]), "Real Time")
        self.breal.on_clicked(self.real)
        self.bplay = Button(plt.axes([0.21, 0.02, 0.04, 0.05]), "x1")
        self.bplay.on_clicked(self.reset)
        self.bfast = Button(plt.axes([0.26, 0.02, 0.04, 0.05]), "Faster")
        self.bfast.on_clicked(self.faster)

        self.bcircle = Button(plt.axes([0.8, 0.02, 0.08, 0.05]), "Circle")
        self.bcircle.on_clicked(self.toggle_circle)
        self.ground = Button(plt.axes([0.9, 0.02, 0.08, 0.05]), "Ground-Track")
        self.ground.on_clicked(self.toggle_groundtrack)

    def propagate(self):

        if self.multiplier is None:
            self.date = Date.now()
        else:
            self.date += self.increment

        for sat in self.sats:
            try:
                sat.propagated = sat.orb.propagate(self.date)
            except ValueError:
                sat.propagated = None
            else:
                # Ground track
                if sat.win_ephem is None:
                    try:
                        sat.win_ephem = WindowEphem(sat.propagated, sat.orb)
                    except ValueError:
                        # In case of faulty windowed ephemeris, disable groundtrack
                        # altogether
                        sat.win_ephem = False

                if sat.win_ephem:
                    sat.win_ephem.propagate(self.date)

    def update_text(self):
        if self.multiplier is None:
            text = "real time"
        else:
            if abs(self.multiplier) == 1:
                adj = ""
                value = abs(self.multiplier)
            elif abs(self.multiplier) > 1:
                adj = "faster"
                value = abs(self.multiplier)
            else:
                adj = "slower"
                value = 1 / abs(self.multiplier)
            sign = "" if self.multiplier > 0 else "-"
            text = "{}x{:0.0f} {}".format(sign, value, adj)

        self.date_text.set_text("{:%Y-%m-%d %H:%M:%S}\n{}".format(self.date, text))
        return self.date_text

    def update_sats(self):

        plot_list = []

        for i, sat in enumerate(self.sats):
            color = self.COLORS[i % len(self.COLORS)]
            # Updating position of the satellite

            if sat.propagated is None:
                continue

            orb = sat.propagated

            orb_sph = orb.copy(form="spherical", frame="ITRF")
            lon, lat = orb2lonlat(orb_sph)
            sat.point.set_data([lon], [lat])
            plot_list.append(sat.point)

            # Updating the label
            sat.text.set_position((lon + 0.75, lat + 0.75))
            plot_list.append(sat.text)

            if self.circle:
                # Updating the circle of visibility
                lonlat = np.degrees(orb2circle(orb_sph))
                lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180
                sat.circle.set_data(lonlat[:, 0], lonlat[:, 1])
                plot_list.append(sat.circle)

            if sat.win_ephem:
                # Ground-track
                sat.gt = []
                for lons, lats in sat.win_ephem.segments():
                    sat.gt.append(
                        self.ax.plot(
                            lons, lats, color=color, alpha=0.5, lw=2, animated=True
                        )[0]
                    )
                    plot_list.append(sat.gt[-1])

        return plot_list

    def update_bodies(self):

        plot_list = []

        # Updating the sun
        sun = get_body("Sun").propagate(self.date).copy(form="spherical", frame="ITRF")
        lon, lat = orb2lonlat(sun)
        self.sun.set_data([lon], [lat])
        plot_list.append(self.sun)

        # Updating the night
        lonlat = np.degrees(orb2circle(sun))
        lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180
        season = -95 if lat > 0 else 95
        lonlat = lonlat[lonlat[:, 0].argsort()]  # Sorting array by ascending longitude

        lonlat = np.concatenate(
            [
                [[-185, season], [-185, lonlat[0, 1]]],
                lonlat,
                [[185, lonlat[-1, 1]], [185, season]],
            ]
        )

        verts = [lonlat]

        # Eclipse (part of the orbit when the satellite is not illuminated by
        # the sun)
        if len(self.sats) == 1:
            orb_sph = self.sats[0].propagated.copy(form="spherical", frame="ITRF")
            virt_alt = Earth.r * orb_sph.r / np.sqrt(orb_sph.r ** 2 - Earth.r ** 2)
            theta = sun.theta + np.pi
            phi = -sun.phi
            lonlat = np.degrees(circle(virt_alt, theta, phi))
            lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180

            if all(abs(lonlat[:, 0]) < 175):
                # This deals with the case when the umbra is between -180 and 180° of
                # longitude
                verts.append(lonlat)
            else:
                pos_lonlat = lonlat.copy()
                neg_lonlat = lonlat.copy()

                pos_lonlat[pos_lonlat[:, 0] < 0, 0] += 360
                neg_lonlat[neg_lonlat[:, 0] > 0, 0] -= 360

                min_lon = min(pos_lonlat[:, 0])
                max_lon = max(neg_lonlat[:, 0])

                lonlat = np.concatenate([neg_lonlat, pos_lonlat])

                if abs(min_lon - max_lon) > 30:
                    # This deals with the case when the umbra is spread between
                    # the east-west edges of the map, but not the north and south
                    # ones
                    verts.append(lonlat)
                else:
                    # This deals with the case when the umbra is spread between
                    # east west and also north or south

                    # sort by ascending longitude
                    lonlat = lonlat[lonlat[:, 0].argsort()]

                    west_lat = lonlat[0, 1]
                    east_lat = lonlat[-1, 1]

                    v = np.concatenate(
                        [
                            [[-360, season], [-360, west_lat]],
                            lonlat,
                            [[360, east_lat], [360, season]],
                        ]
                    )

                    verts.append(v)

        self.night.set_verts(verts)
        plot_list.append(self.night)

        # Updating the moon
        moon = (
            get_body("Moon").propagate(self.date).copy(frame="ITRF", form="spherical")
        )
        lon, lat = orb2lonlat(moon)
        self.moon.set_data([lon], [lat])
        plot_list.append(self.moon)

        return plot_list

    def __call__(self, frame):

        self.propagate()

        plot_list = []
        plot_list.append(self.update_text())
        plot_list.extend(self.update_sats())
        plot_list.extend(self.update_bodies())

        return plot_list

    @property
    def increment(self):
        return timedelta(seconds=self.multiplier * self.interval / 1000)

    def real(self, *args, **kwargs):
        self.multiplier = None

    def reset(self, *args, **kwargs):
        self.multiplier = 1

    def faster(self, *args, **kwargs):

        steps = [2, 2.5, 2]

        if not hasattr(self, "_step"):
            self._step = 0
        else:
            self._step += 1

        if self.multiplier is None:
            self.multiplier = 2
        else:
            self.multiplier *= steps[self._step % len(steps)]

    def slower(self, *args, **kwargs):
        steps = [2, 2.5, 2]

        if not hasattr(self, "_step"):
            self._step = 0
        else:
            self._step += 1

        if self.multiplier is None:
            self.multiplier = 1 / 2
        else:
            self.multiplier /= steps[self._step % len(steps)]

    def reverse(self, *args, **kwargs):
        if self.multiplier is None:
            self.multiplier = -1
        else:
            self.multiplier *= -1

    def toggle_groundtrack(self, *args, **kwargs):
        status = isinstance(self.sats[0].win_ephem, WindowEphem)

        for sat in self.sats:
            if status:
                sat.win_ephem = False
            else:
                sat.win_ephem = None
                # Force recomputation of the window ephemeris

    def toggle_circle(self, *args, **kwargs):

        if self.circle is True:
            for sat in self.sats:
                sat.circle.set_data([], [])

        self.circle ^= True
