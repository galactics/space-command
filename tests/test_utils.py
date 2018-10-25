import numpy as np
from pytest import mark

from space.utils import circle


@mark.skip
def test_circle():

    alt = 410000 + 6400000

    sat_circle = circle(alt, 0, 0.)


    assert len(sat_circle) == 360

    azims = np.array([0, 90, 122, 147, 164, 188, 203, 215, 239, 247])
    elevs = np.array([80, 36, 2, 7.4, 9.5, 16.1, 10.7, 15.7, 20, 20.2])
    
    mask = (2 * np.pi - np.radians(azims[::-1])), np.radians(elevs[::-1])
    sat_circle = circle(alt, 0., 0., mask=mask)

    assert len(sat_circle) == 10

    sat_circle = circle(alt, 0, np.radians(70.))

    assert len(sat_circle) == 360
    
    # import matplotlib.pyplot as plt
    # lon, lat = np.degrees(list(zip(*sat_circle)))
    # lon = ((lon + 180) % 360) - 180
    # plt.plot(lon, lat, '.', ms=2)
    # plt.xlim([-180, 180])
    # plt.ylim([-90, 90])
    # plt.show()