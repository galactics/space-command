import re
import sys
from textwrap import dedent
from docopt import docopt as true_docopt
from numpy import cos, sin, arccos, arcsin, pi, ones, linspace, copysign, degrees

from beyond.constants import Earth


__all__ = ["circle", "orb2circle", "docopt", "parse_date", "parse_timedelta"]


def parse_date(txt, fmt=None):
    """

    Args:
        txt (str):  Text to convert to a date
        fmt (str):  Format in which the date is expressed. if ``None``
                    tries %Y-%m-%dT%H:%M:%S, and then %Y-%m-%d
    Return:
        beyond.dates.date.Date:
    Raise:
        ValueError

    Examples:
        >>> print(parse_date("2018-12-25T00:23:56"))
        2018-12-25T00:23:56 UTC
        >>> print(".", parse_date("now"))  # The dot is here to trigger the ellipsis
        . ... UTC
        >>> print(".", parse_date("midnight"))  # The dot is here to trigger the ellipsis
        . ...T00:00:00 UTC
        >>> print(parse_date("naw"))
        Traceback (most recent call last):
          ...
        ValueError: time data 'naw' does not match formats '%Y-%m-%d' or '%Y-%m-%dT%H:%M:%S'
    """

    from .clock import Date

    fmts = {"full": "%Y-%m-%dT%H:%M:%S", "date": "%Y-%m-%d"}

    if not isinstance(txt, str):
        raise TypeError("type 'str' expected, got '{}' instead".format(type(txt)))

    txt, _, scale = txt.partition(" ")

    if not scale:
        scale = Date.DEFAULT_SCALE

    if txt == "now":
        date = Date.now(scale=scale)
    elif txt == "midnight":
        date = Date(Date.now().d, scale=scale)
    elif txt == "tomorrow":
        date = Date(Date.now().d + 1, scale=scale)
    elif fmt is None:
        try:
            date = Date.strptime(txt, fmts["full"], scale=scale)
        except ValueError:
            try:
                date = Date.strptime(txt, fmts["date"], scale=scale)
            except ValueError as e:
                raise ValueError(
                    "time data '{0}' does not match formats '{1[date]}' or '{1[full]}'".format(
                        txt, fmts
                    )
                )

    else:
        date = Date.strptime(txt, fmts.get(fmt, fmt), scale=scale)

    return date


def parse_timedelta(txt, negative=False):
    """Convert a timedelta input string into a timedelta object

    Args:
        txt (str): 
        negative (bool): Allow for negative value
    Return:
        timedelta:
    Raise:
        ValueError: nothing can be parsed from the string

    Examples:
        >>> print(parse_timedelta('1w3d6h25.52s'))
        10 days, 6:00:25.520000
        >>> print(parse_timedelta('2d12m30s'))
        2 days, 0:12:30
        >>> print(parse_timedelta('20s'))
        0:00:20
        >>> print(parse_timedelta(''))
        Traceback (most recent call last):
          ...
        ValueError: No timedelta found in ''
        >>> print(parse_timedelta('20'))
        Traceback (most recent call last):
          ...
        ValueError: No timedelta found in '20'
    """

    from .clock import timedelta

    m = re.search(
        r"(?P<sign>-)?((?P<weeks>\d+)w)?((?P<days>[\d.]+)d)?((?P<hours>[\d.]+)h)?((?P<minutes>[\d.]+)m)?((?P<seconds>[\d.]+)s)?",
        txt,
    )

    sign = 1
    if negative and m.group("sign") is not None:
        sign = -1
    weeks = float(m.group("weeks")) if m.group("weeks") is not None else 0
    days = float(m.group("days")) if m.group("days") is not None else 0
    hours = float(m.group("hours")) if m.group("hours") is not None else 0
    minutes = float(m.group("minutes")) if m.group("minutes") is not None else 0
    seconds = float(m.group("seconds")) if m.group("seconds") is not None else 0

    days += 7 * weeks
    seconds += minutes * 60 + hours * 3600

    if days == seconds == 0:
        raise ValueError("No timedelta found in '{}'".format(txt))

    return sign * timedelta(days, seconds)


def docopt(doc, argv=None, **kwargs):
    argv = argv if argv else sys.argv[2:]
    return true_docopt(dedent("    " + doc), argv=argv, **kwargs)


def orb2circle(orb, mask=0):
    """Compute a circle of visibility of an orbit

    Args:
        orb (Orbit):
        mark (float):
    Return:
        list: List of longitude/latitude couple (in radians)
    """
    return circle(*orb.copy(form="spherical")[:3])


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
        dlon = arccos(
            -(sin(point_lat) * sin(lat) - cos(alpha)) / (cos(point_lat) * cos(lat))
        )

        if theta < pi:
            point_lon = lon - dlon
        elif abs(lat) + alpha >= pi / 2:
            # if the circle includes a pole
            point_lon = lon + dlon
        else:
            point_lon = lon - (2 * pi - dlon)

        result.append((point_lon, point_lat))

    return result


def orb2lonlat(orb):
    orb = orb.copy(form="spherical", frame="ITRF")
    lon, lat = degrees(orb[1:3])
    lon = ((lon + 180) % 360) - 180
    return lon, lat


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

    return sign * (d + m / 60.0 + s / 3600.0)


def hms2deg(h, m, s):
    """Convert from hour, minutes, seconds to degrees

    Args:
        h (int)
        m (int)
        s (float)
    Return:
        float
    """

    return h * 360 / 24 + m / 60.0 + s / 3600.0


def humanize(byte_size):

    cursor = byte_size
    divisor = 1024

    for i in "B KiB MiB GiB".split():
        cursor, remainder = divmod(byte_size, divisor)
        if cursor < 1:
            break
        byte_size = cursor + remainder / divisor

    return "{:7.2f} {}".format(byte_size, i)
