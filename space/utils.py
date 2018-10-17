import sys
from textwrap import dedent
from docopt import docopt as true_docopt
from numpy import cos, sin, arccos, arcsin, pi, ones, linspace, copysign

from beyond.constants import Earth


__all__ = ['circle', 'docopt']


def docopt(doc, argv=None, **kwargs):
    argv = argv if argv else sys.argv[2:]
    return true_docopt(dedent("    " + doc), argv=argv, **kwargs)


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


def deg2dmstuple(deg):
    sign = copysign(1, deg)
    mnt, sec = divmod(abs(deg) * 3600, 60)
    deg, mnt = divmod(mnt, 60)
    return int(sign * deg), int(mnt), sec


def deg2dms(deg, heading=None, sec_prec=3):
    """Convert from degrees to degrees, minutes seconds

    Args:
        deg (float): angle in degrees
        heading (str): 'latitude' or 'longitude'
        sec_prec (int): precision given to the seconds
    return:
        str: String representation of the angle

    Example:
        >>> print(deg2dms(43.56984611, 'latitude'))
        N43°34'11.446"
        >>> print(deg2dms(-43.56984611, 'latitude'))
        S43°34'11.446"
        >>> print(deg2dms(3.77059194, 'longitude'))
        E3°46'14.131"
        >>> print(deg2dms(-3.77059194, 'longitude'))
        W3°46'14.131"
    """

    d, m, s = deg2dmstuple(deg)

    if heading:
        if "lon" in heading:
            head = "E" if d >= 0 else "W"
        elif "lat" in heading:
            head = "N" if d >= 0 else "S"

        txt = "{}{}°{}'{:0.{}f}\"".format(head, abs(d), m, s, sec_prec)
    else:
        txt = "{}°{}'{:0.{}f}\"".format(d, m, s, sec_prec)

    return txt


def dms_split(dms):
    if "S" in dms or "W" in dms:
        sign = -1
    else:
        sign = 1

    dms = dms.strip().strip("NSEW")

    d, _, rest = dms.partition("°")
    m, _, rest = rest.partition("'")
    s, _, rest = rest.partition('"')

    return int(d), int(m), float(s), sign


def dms2deg(dms):
    """Convert from degrees, minutes, seconds text representation to degrees

    Args:
        dms (str): String to be converted to degrees
    Return:
        float: signed with respect to N-S/E-W
    Example:
        >>> print("{:0.8f}".format(dms2deg("N43°34'11.446\\"")))
        43.56984611
        >>> print("{:0.8f}".format(dms2deg("S43°34'11.446\\"")))
        -43.56984611
        >>> print("{:0.8f}".format(dms2deg("E3°46'14.131\\"")))
        3.77059194
        >>> print("{:0.8f}".format(dms2deg("W3°46'14.131\\"")))
        -3.77059194
    """
    d, m, s, sign = dms_split(dms)

    return sign * (d + m / 60. + s / 3600.)


def hms2deg(h, m, s):
    return h * 360 / 24 + m / 60. + s / 3600.
