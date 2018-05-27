
from numpy import degrees, pi, radians

from beyond.frames import get_frame, create_station

from .config import config
from .utils import dms2deg, deg2dms


class StationDatabase:

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
            for abbr, caract in config['stations'].items():

                caract['parent_frame'] = get_frame(caract['parent_frame'])
                full_name = caract.pop('name')

                mask = caract.get('mask')
                if mask:
                    # reverse direction of the mask to put it in counterclockwise
                    # to comply with the mathematical definition
                    caract['mask'] = (2 * pi - radians(mask['azims'][::-1])), radians(mask['elevs'][::-1])

                caract.setdefault('delay', True)

                self._stations[abbr] = create_station(abbr, **caract)
                self._stations[abbr].abbr = abbr
                self._stations[abbr].full_name = full_name

        return self._stations

    @classmethod
    def get(cls, name):

        self = cls()

        try:
            return get_frame(name)
        except ValueError:
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
      space-stations [create]

    Options
      create  Interactively create a station

    If no option is provided, list all stations available
    """

    from .utils import docopt

    args = docopt(space_stations.__doc__)

    station = StationDatabase()

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

        StationDatabase.save({
            abbr: {
                "name": name,
                "latlonalt": (latitude, longitude, altitude),
                "parent_frame": "WGS84"
            }
        })
    else:
        for station in station.list().values():
            print(station.name)
            print("-" * len(station.name))
            lat, lon, alt = station.latlonalt
            lat, lon = degrees([lat, lon])
            print("abbr:     {}".format(station.abbr))
            print("altitude: {} m\nposition: {}, {}".format(alt, deg2dms(lat, "lat"), deg2dms(lon, "lon")))
            print()
