import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

from ..station import StationDb


def set_background(stations="black"):
    """Display the map background (earth and stations)

    Args:
        stations (str): If non empty, provides the matplotlib color to be
            used for stations marks. To disable stations marks, set to
            ``False``
    """

    path = Path(__file__).parent.parent / "static/earth.png"
    im = plt.imread(str(path))
    plt.imshow(im, extent=[-180, 180, -90, 90])
    plt.xlim([-180, 180])
    plt.ylim([-90, 90])
    plt.grid(True, linestyle=":", alpha=0.4)
    plt.xticks(range(-180, 181, 30))
    plt.yticks(range(-90, 91, 30))

    if stations:
        for station in StationDb.list().values():
            lat, lon = np.degrees(station.latlonalt[:-1])
            plt.plot([lon], [lat], "+", color=stations)
            plt.text(lon + 1, lat + 1, station.abbr, color=stations)
