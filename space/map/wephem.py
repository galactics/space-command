import numpy as np

from beyond.orbits import Ephem

from ..utils import orb2lonlat


class WindowEphem(Ephem):
    """Ephemeris used to display the ground-track of the orbit

    When propagating, this ephemeris keeps +/- one orbital period
    around the given date

    Includes a caching mechanism, in order to keep in memory
    locations already computed.
    """

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

            # The new date is between already computed points
            # We only need to compute new points at the edges

            date_diff = (date - self.start) / self.step
            date_i = int(date_diff)
            mid = len(self) // 2
            new = (date_i - mid) * self.step

            if date_i > mid:
                # Future
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
                # Past
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
            # The new date is not between already computed points
            # We have to compute a new set of points from the orbit
            self._orbits = list(
                self.orb.ephemeris(
                    start=date - self.span / 2,
                    stop=self.span,
                    step=self.step,
                    strict=False,
                )
            )

    def segments(self):
        """Cut the ephemeris in segments for easy display
        """

        lons, lats = [], []
        segments = []
        prev_lon, prev_lat = None, None
        for win_orb in self:
            lon, lat = orb2lonlat(win_orb)

            # Creation of multiple segments in order to not have a ground track
            # doing impossible paths
            if prev_lon is None:
                lons = []
                lats = []
                segments.append((lons, lats))
            elif win_orb.infos.kep.i < np.pi / 2 and (
                np.sign(prev_lon) == 1 and np.sign(lon) == -1
            ):
                lons.append(lon + 360)
                lats.append(lat)
                lons = [prev_lon - 360]
                lats = [prev_lat]
                segments.append((lons, lats))
            elif win_orb.infos.kep.i > np.pi / 2 and (
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

        return segments
