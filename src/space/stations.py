
from numpy import degrees, pi

from beyond.frames.frame import create_station, get_frame

from .config import config


def dms2deg(angle):

    if angle[0] in 'NE':
        sign = 1
    else:
        sign = -1

    d, _, rest = angle[1:].partition('°')
    m, _, rest = rest.partition("'")
    s = rest.replace('"', "")

    return sign * (int(d) + int(m) / 60. + float(s) / 3600.)


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
                for i, elem in enumerate(caract['latlonalt'][:2]):
                    if type(elem) is str:
                        caract['latlonalt'][i] = dms2deg(elem)

                caract['parent_frame'] = get_frame(caract['parent_frame'])
                full_name = caract.pop('name')
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
    """\
    List available stations

    Usage:
      space-stations [create]

    Options
      create  Interactively create a station

    If no option is provided, list all stations available
    """

    from textwrap import dedent
    from docopt import docopt

    args = docopt(dedent(space_stations.__doc__), argv=argv)

    station = StationDatabase()

    if args['create']:
        print("Create a new station")
        abbr = input("Abbreviation : ")
        name = input("Name : ")
        latitude = float(input("Latitude : "))
        longitude = float(input("Longitude : "))
        altitude = float(input("Altitude : "))

        StationDatabase.save({
            abbr: {
                "name": name,
                "latlonalt": (latitude, longitude, altitude),
                "orientation": "N",
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
            print("altitude: {} m\nposition: {:8.5f}°N, {:9.5f}°E".format(alt, lat, lon))

            choices = {
                0.: "South",
                pi: "North"
            }

            orient = choices.get(station.orientation, 180 - degrees(station.orientation))

            print("orient:  ", orient)
            print()
