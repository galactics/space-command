import sys
import numpy as np
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button

from beyond.constants import Earth
from beyond.env.solarsystem import get_body
from beyond.orbits import Orbit, Ephem

from .utils import circle
from .station import StationDb
from .clock import Date, timedelta


class WindowEphem(Ephem):
    def __init__(self, orb, ref_orb):
        """
        Args:
            orb (Orbit) : Used as cursor
            ref_orb (Orbit or Ephem): Used to propagate
        """

        self.span = orb.infos.period * 2
        start = orb.date - self.span / 2
        stop = start + self.span
        self.orb = ref_orb
        self.step = orb.infos.period / 100

        orbs = ref_orb.ephemeris(start=start, stop=stop, step=self.step, strict=False)
        super().__init__(orbs)

    def propagate(self, date):
        if self.start < date < self.stop:
            date_diff = (date - self.start) / self.step
            date_i = int(date_diff)
            mid = len(self) // 2
            new = (date_i - mid) * self.step

            if date_i > mid:
                orbs = list(
                    self.orb.ephemeris(
                        start=self.stop + self.step,
                        stop=new,
                        step=self.step,
                        strict=False,
                    )
                )
                for x in orbs:
                    self._orbits.pop(0)
                    self._orbits.append(x)
            elif date_i < mid - 1:
                orbs = list(
                    self.orb.ephemeris(
                        start=self.start - self.step,
                        stop=new,
                        step=-self.step,
                        strict=False,
                    )
                )
                for x in orbs:
                    self._orbits.pop()
                    self._orbits.insert(0, x)
        else:
            self._orbits = list(
                self.orb.ephemeris(
                    start=date - self.span / 2,
                    stop=self.span,
                    step=self.step,
                    strict=False,
                )
            )


class SatAnim:

    COLORS = "r", "g", "b", "c", "m", "y", "k", "w"

    def __init__(self, sats):
        self.sats = sats
        self.multiplier = None
        self.interval = 200

        mpl.rcParams["toolbar"] = "None"

        path = Path(__file__).parent / "static/earth.png"
        im = plt.imread(str(path))
        self.fig = plt.figure(figsize=(15.2, 8.2))
        self.ax = plt.subplot(111)
        plt.imshow(im, extent=[-180, 180, -90, 90])
        plt.xlim([-180, 180])
        plt.ylim([-90, 90])
        plt.grid(True, linestyle=":", alpha=0.4)
        plt.xticks(range(-180, 181, 30))
        plt.yticks(range(-90, 91, 30))
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.1)

        self.sun, = plt.plot(
            [], [], "yo", markersize=10, markeredgewidth=0, animated=True, zorder=2
        )
        self.moon, = plt.plot(
            [], [], "wo", markersize=10, markeredgewidth=0, animated=True, zorder=2
        )
        self.night = plt.fill_between(
            [], [], color="k", alpha=0.3, lw=0, animated=True, zorder=1
        )
        self.date_text = plt.text(-175, 80, "")

        for station in StationDb.list().values():
            lat, lon = np.degrees(station.latlonalt[:-1])
            plt.plot([lon], [lat], "k+")
            plt.text(lon + 1, lat + 1, station.abbr)

        # For each satellite, initialisation of graphical representation
        for i, sat in enumerate(self.sats):
            color = self.COLORS[i % len(self.COLORS)]

            sat.point, = plt.plot(
                [], [], "o", ms=5, color=color, animated=True, zorder=10
            )
            sat.circle, = plt.plot(
                [], [], ".", ms=2, color=color, animated=True, zorder=10
            )
            sat.text = plt.text(0, 0, sat.name, color=color, animated=True, zorder=10)
            sat.win_ephem = None

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

        self.ground = Button(plt.axes([0.9, 0.02, 0.08, 0.05]), "Ground-Track")
        self.ground.on_clicked(self.toggle_groundtrack)

        self.ani = FuncAnimation(self.fig, self, interval=self.interval, blit=True)

    def __call__(self, frame):

        plot_list = []

        date = self.date()

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

        self.date_text.set_text("{:%Y-%m-%d %H:%M:%S}\n{}".format(date, text))
        plot_list.append(self.date_text)

        for i, sat in enumerate(self.sats):
            color = self.COLORS[i % len(self.COLORS)]
            # Updating position of the satellite
            orb = sat.orb.propagate(date)
            orb_sph = orb.copy(form="spherical", frame="ITRF")
            lon, lat = self.lonlat(orb_sph)
            sat.point.set_data([lon], [lat])
            plot_list.append(sat.point)

            # Updating the label
            sat.text.set_position((lon + 0.75, lat + 0.75))
            plot_list.append(sat.text)

            # Updating the circle of visibility
            lonlat = np.degrees(circle(*orb_sph[:3]))
            lonlat[:, 0] = ((lonlat[:, 0] + 180) % 360) - 180
            sat.circle.set_data(lonlat[:, 0], lonlat[:, 1])
            plot_list.append(sat.circle)

            # Ground track
            if sat.win_ephem is None:
                try:
                    sat.win_ephem = WindowEphem(orb, sat.orb)
                except ValueError:
                    # In case of faulty windowed ephemeris, disable groundtrack
                    # altogether
                    sat.win_ephem = False

            if sat.win_ephem:
                sat.win_ephem.propagate(date)

                lons, lats = [], []
                segments = []
                prev_lon, prev_lat = None, None
                for win_orb in sat.win_ephem:
                    lon, lat = self.lonlat(win_orb.copy(form="spherical", frame="ITRF"))

                    # Creation of multiple segments in order to not have a ground track
                    # doing impossible paths
                    if prev_lon is None:
                        lons = []
                        lats = []
                        segments.append((lons, lats))
                    elif orb.infos.kep.i < np.pi / 2 and (
                        np.sign(prev_lon) == 1 and np.sign(lon) == -1
                    ):
                        lons.append(lon + 360)
                        lats.append(lat)
                        lons = [prev_lon - 360]
                        lats = [prev_lat]
                        segments.append((lons, lats))
                    elif orb.infos.kep.i > np.pi / 2 and (
                        np.sign(prev_lon) == -1 and np.sign(lon) == 1
                    ):
                        lons.append(lon - 360)
                        lats.append(lat)
                        lons = [prev_lon + 360]
                        lats = [prev_lat]
                        segments.append((lons, lats))
                    elif abs(prev_lon) > 150 and (np.sign(prev_lon) != np.sign(lon)):
                        lons.append(lon - 360)
                        lats.append(lat)
                        lons = [prev_lon + 360]
                        lats = [prev_lat]
                        segments.append((lons, lats))

                    lons.append(lon)
                    lats.append(lat)
                    prev_lon = lon
                    prev_lat = lat

                sat.gt = []
                for lons, lats in segments:
                    sat.gt.append(
                        self.ax.plot(
                            lons, lats, color=color, alpha=0.5, lw=2, animated=True
                        )[0]
                    )
                    plot_list.append(sat.gt[-1])

        # Updating the sun
        sun = get_body("Sun").propagate(date).copy(form="spherical", frame="ITRF")
        lon, lat = self.lonlat(sun)
        self.sun.set_data([lon], [lat])
        plot_list.append(self.sun)

        # Updating the night
        lonlat = np.degrees(circle(*sun[:3]))
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
        plot_list.insert(0, self.night)

        # Updating the moon
        moon = get_body("Moon").propagate(date).copy(frame="ITRF", form="spherical")
        lon, lat = self.lonlat(moon)
        self.moon.set_data([lon], [lat])
        plot_list.append(self.moon)

        return plot_list

    @classmethod
    def lonlat(cls, orb):
        orb = orb.copy(form="spherical", frame="ITRF")
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


def space_map(*argv):
    """Animated map of earth with ground track of satellites

    Usage:
      space-map (- | <satellite>...) [-g]

    Option:
      <satellite>   Name of the satellites you want to display.
      -             If used, the orbit should be provided as stdin in TLE or
                    CCSDS format
    """

    from .utils import docopt
    from .sat import Sat

    args = docopt(space_map.__doc__)
    sats = list(
        Sat.from_input(*args["<satellite>"], text=sys.stdin.read() if args["-"] else "")
    )

    sat_anim = SatAnim(sats)

    plt.show()
