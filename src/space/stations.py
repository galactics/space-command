
import json
from numpy import degrees, pi

from beyond.config import config
from beyond.frames.frame import create_station, get_frame


def dms2deg(angle):

    if angle[0] in 'NE':
        sign = 1
    else:
        sign = -1

    d, _, rest = angle[1:].partition('°')
    m, _, rest = rest.partition("'")
    s = rest.replace('"', "")

    return sign * (int(d) + int(m) / 60. + float(s) / 3600.)


def list_stations():

    if not hasattr(list_stations, 'stations'):

        list_stations.stations = {}
        station_file = config.folder / "stations.json"
        for name, caract in json.load(station_file.open()).items():
            for i, elem in enumerate(caract['latlonalt'][:2]):
                if type(elem) is str:
                    caract['latlonalt'][i] = dms2deg(elem)

            caract['parent_frame'] = get_frame(caract['parent_frame'])
            abbr = caract.pop('abbr')
            list_stations.stations[abbr] = create_station(name, **caract)
            list_stations.stations[abbr].abbr = abbr

    return list_stations.stations


def get_station(name):

    try:
        return get_frame(name)
    except ValueError:
        if name not in list_stations().keys():
            raise
        return list_stations()[name]


def space_stations(*argv):
    """\
    List available stations
    """

    for station in list_stations().values():
        print(station.name)
        print("-" * len(station.name))
        lat, lon, alt = station.latlonalt
        lat, lon = degrees([lat, lon])
        print("   abbr:     {}".format(station.abbr))
        print("   altitude: {} m\n   position: {:8.5f}°N, {:9.5f}°E".format(alt, lat, lon))

        choices = {
            0.: "South",
            pi: "North"
        }

        orient = choices.get(station.orientation, 180 - degrees(station.orientation))

        print("  ", "orient:  ", orient)
