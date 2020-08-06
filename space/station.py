import logging
from numpy import degrees, pi, radians

from beyond.frames import get_frame, create_station
from beyond.errors import UnknownFrameError

from .wspace import ws
from .utils import dms2deg, deg2dms


log = logging.getLogger(__name__)


class StationDb:
    def __new__(cls):

        if not hasattr(cls, "_instance"):
            # Singleton
            cls._instance = super().__new__(cls)

        return cls._instance

    @classmethod
    def list(cls):

        self = cls()

        if not hasattr(self, "_stations"):

            self._stations = {}
            for abbr, charact in ws.config["stations"].items():

                charact["parent_frame"] = get_frame(charact["parent_frame"])
                full_name = charact.pop("name")
                mask = charact.get("mask")
                if mask:
                    # reverse direction of the mask to put it in counterclockwise
                    # to comply with the mathematical definition
                    charact["mask"] = (
                        (2 * pi - radians(mask["azims"][::-1])),
                        radians(mask["elevs"][::-1]),
                    )

                # Deletion of all unknown characteristics from the charact dict
                # and conversion to object attributes (they may be used by addons)
                extra_charact = {}
                for key in list(charact.keys()):
                    if key not in ("parent_frame", "latlonalt", "mask"):
                        extra_charact[key] = charact.pop(key)

                self._stations[abbr] = create_station(abbr, **charact)
                self._stations[abbr].abbr = abbr
                self._stations[abbr].full_name = full_name

                for key, value in extra_charact.items():
                    setattr(self._stations[abbr], key, value)

        return self._stations

    @classmethod
    def get(cls, name):

        self = cls()

        try:
            return get_frame(name)
        except UnknownFrameError:
            if name not in self.list().keys():
                raise
            return self.list()[name]

    @classmethod
    def save(cls, station):
        self = cls()

        ws.config["stations"].update(station)
        ws.config.save()

        if hasattr(self, "_stations"):
            del self._stations


def wshook(cmd, *args, **kwargs):

    if cmd in ("init", "full-init"):
        name = "TLS"

        ws.config.setdefault("stations", {})

        try:
            StationDb.get(name)
        except UnknownFrameError:
            StationDb.save(
                {
                    name: {
                        "latlonalt": [43.604482, 1.443962, 172.0],
                        "name": "Toulouse",
                        "parent_frame": "WGS84",
                    }
                }
            )
            log.info("Station {} created".format(name))
        else:
            log.warning("Station {} already exists".format(name))


def space_station(*argv):
    """Stations management

    Usage:
      space-station list [--map] [<abbr>]
      space-station create <abbr> <name> <lat> <lon> <alt>

    Options
      list       List available stations
      create     Interactively create a station
      <abbr>     Abbreviation
      <name>     Name of the station
      <lat>      Latitude in degrees
      <lon>      Longitude in degrees
      <alt>      Altitude in meters
      -m, --map  Display the station on a map

    Latitude and longitude both accept degrees as float or as
    degrees, minutes and seconds of arc (e.g. 43°25"12')
    """

    from pathlib import Path
    import matplotlib.pyplot as plt

    from .utils import docopt
    from .map.background import set_background

    args = docopt(space_station.__doc__)

    station = StationDb()

    if args["create"]:
        abbr = args["<abbr>"]
        name = args["<name>"]
        latitude = args["<lat>"]
        longitude = args["<lon>"]
        altitude = args["<alt>"]

        if "°" in latitude:
            latitude = dms2deg(latitude)
        else:
            latitude = float(latitude)

        if "°" in longitude:
            longitude = dms2deg(longitude)
        else:
            longitude = float(longitude)

        altitude = float(altitude)

        log.info("Creation of station '{}' ({})".format(name, abbr))
        log.debug(
            "{} {}, altitude : {} m".format(
                deg2dms(latitude, "lat"), deg2dms(longitude, "lon"), altitude
            )
        )
        StationDb.save(
            {
                abbr: {
                    "name": name,
                    "latlonalt": (latitude, longitude, altitude),
                    "parent_frame": "WGS84",
                }
            }
        )
    else:

        stations = []

        for station in sorted(station.list().values(), key=lambda x: x.abbr):

            if args["<abbr>"] and station.abbr != args["<abbr>"]:
                continue

            print(station.name)
            print("-" * len(station.name))
            lat, lon, alt = station.latlonalt
            lat, lon = degrees([lat, lon])
            print("name:     {}".format(station.full_name))
            print(
                "altitude: {} m\nposition: {}, {}".format(
                    alt, deg2dms(lat, "lat"), deg2dms(lon, "lon")
                )
            )
            print()

            stations.append((station.name, lat, lon))

        if args["--map"]:
            plt.figure(figsize=(15.2, 8.2))
            set_background()
            plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
            plt.show()
