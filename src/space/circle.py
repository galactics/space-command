
from numpy import cos, sin, arccos, arcsin, pi, ones, linspace

from beyond.constants import Earth


__all__ = ['circle']


def circle(alt, lon, lat, mask=0):
    """Compute the visibility circle

    This function may be used for both station and satellites visibility
    circles.

    Args:
        alt (float): Altitude of the satellite
        lon (float): Longitude of the center of the circle in radians
        lat (float): Latitude of the center of the circle in radians
        mask (float):
    Returns:
        list: List of longitude/latitude couple (in radians)
    """

    if isinstance(mask, (int, float)):
        mask = linspace(0, pi * 2, 360), ones(360) * mask

    result = []

    # we go through the azimuts
    for theta, phi in zip(*mask):

        # half-angle of sight
        alpha = arccos(Earth.r * cos(phi) / alt) - phi

        theta += 0.0001  # for nan avoidance

        # Latitude
        point_lat = arcsin(sin(lat) * cos(alpha) + cos(lat) * sin(alpha) * cos(theta))

        # Longitude
        dlon = arccos(-(sin(point_lat) * sin(lat) - cos(alpha)) / (cos(point_lat) * cos(lat)))

        if theta < pi:
            point_lon = lon - dlon
        elif abs(lat) + alpha >= pi / 2:
            # if the circle includes a pole
            point_lon = lon + dlon
        else:
            point_lon = lon - (2 * pi - dlon)

        result.append((point_lon, point_lat))

    return result

if __name__ == "__main__":

    import numpy as np
    import matplotlib.pyplot as plt

    def degcir(*args, **kwargs):
        c = np.degrees(circle(*args, **kwargs))
        c[:, 0] = ((c[:, 0] + 180) % 360) - 180
        return c

    altlonlat = 36000000 + Earth.r, 0, np.pi / 4.

    m = [[0, 44.9, 45, 75, 75.1, 119.9, 120, 140, 140.1, 360], [0, 0, -50, -50, 0, 0, 30, 30, 0, 0]]

    azim = np.arange(0, 360)
    elev = np.interp(azim, m[0], m[1])

    m = azim, elev

    c0 = degcir(*altlonlat)
    plt.plot(c0[:, 0], c0[:, 1], ":", label="0 deg")
    c1 = degcir(*altlonlat, mask=np.radians(5))
    plt.plot(c1[:, 0], c1[:, 1], ":", label="5 deg")
    c2 = degcir(*altlonlat, mask=np.radians(m))
    plt.plot(c2[:, 0], c2[:, 1], label="mask")

    plt.axis('equal')
    plt.xlim(-180, 180)
    plt.ylim(-90, 90)

    plt.legend()

    plt.figure()

    x = np.linspace(380000 + Earth.r, 8000000 + Earth.r, 50)
    y1 = np.pi / 2 - np.arcsin(Earth.r / x)
    y2 = np.arccos(Earth.r / x)

    plt.plot(x, y1)
    plt.plot(x, y2, "o")
    plt.show()
