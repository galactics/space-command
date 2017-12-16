
from numpy import cos, sin, arccos, arcsin, pi, ones, linspace

from beyond.constants import Earth
from beyond.utils.ccsds import CCSDS

from .tle import Tle


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


def parse_orbits(txt):

    orbits = [tle.orbit() for tle in Tle.from_string(txt)]
    if not orbits:
        orbits = [CCSDS.loads(txt)]

    return orbits
