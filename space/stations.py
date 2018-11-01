
from numpy import degrees, pi, radians

from beyond.frames import get_frame, create_station
from beyond.errors import UnknownFrameError

from .config import config
from .utils import dms2deg, deg2dms


class StationDb:

    def __new__(cls):

        if not hasattr(cls, '_instance'):
            # Singleton
            cls._instance = super().__new__(cls)

        return cls._instance

    @classmethod
    def list(cls):

        self = cls()

        if not hasattr(self, '_stations'):

            self._stations = {}
            for abbr, charact in config['stations'].items():

                charact['parent_frame'] = get_frame(charact['parent_frame'])
                full_name = charact.pop('name')
                mask = charact.get('mask')
                if mask:
                    # reverse direction of the mask to put it in counterclockwise
                    # to comply with the mathematical definition
                    charact['mask'] = (2 * pi - radians(mask['azims'][::-1])), radians(mask['elevs'][::-1])

                # Deletion of all unknown characteristics from the charact dict
                # and conversion to object attributes (they may be used by addons)
                extra_charact = {}
                for key in list(charact.keys()):
                    if key not in ('parent_frame', 'latlonalt', 'mask'):
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

        config['stations'].update(station)
        config.save()

        if hasattr(self, "_stations"):
            del self._stations


def space_stations(*argv):
    """List available stations

    Usage:
      space-stations [--map]
      space-stations create

    Options
      create     Interactively create a station
      -m, --map  Display the stations on a map

    If no option is provided, list all stations available
    """

    from pathlib import Path
    import matplotlib.pyplot as plt


    from .utils import docopt

    args = docopt(space_stations.__doc__)

    station = StationDb()

    if args['create']:
        print("Create a new station")
        abbr = input("Abbreviation : ")
        name = input("Name : ")

        latitude = input("Latitude : ")
        if "°" in latitude:
            latitude = dms2deg(latitude)
        else:
            latitude = float(latitude)

        longitude = input("Longitude : ")
        if "°" in longitude:
            longitude = dms2deg(longitude)
        else:
            longitude = float(longitude)

        altitude = float(input("Altitude : "))

        StationDb.save({
            abbr: {
                "name": name,
                "latlonalt": (latitude, longitude, altitude),
                "parent_frame": "WGS84"
            }
        })
    else:

        stations = []

        for station in sorted(station.list().values(), key=lambda x: x.abbr):
            print(station.name)
            print("-" * len(station.name))
            lat, lon, alt = station.latlonalt
            lat, lon = degrees([lat, lon])
            print("name:     {}".format(station.full_name))
            print("altitude: {} m\nposition: {}, {}".format(alt, deg2dms(lat, "lat"), deg2dms(lon, "lon")))
            print()

            stations.append((station.name, lat, lon))

        if args['--map']:
            path = Path(__file__).parent / "static/earth.png"
            im = plt.imread(str(path))
            plt.figure(figsize=(15.2, 8.2))
            plt.imshow(im, extent=[-180, 180, -90, 90])
            plt.xlim([-180, 180])
            plt.ylim([-90, 90])
            plt.grid(True, linestyle=':', alpha=0.4)
            plt.xticks(range(-180, 181, 30))
            plt.yticks(range(-90, 91, 30))
            plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.1)

            for name, lat, lon in stations:
                plt.plot([lon], [lat], 'ko')
                plt.text(lon + 1, lat + 1, name)

            plt.show()