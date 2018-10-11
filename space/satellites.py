
import sys
from textwrap import indent

from beyond.orbits import Tle, Ephem, Orbit
from beyond.utils.ccsds import loads


def get_sats(*args, stdin=False):
    from .tle import TleDb, TleNotFound

    if len(args) > 0:
        try:
            sats = [TleDb.get(name=sat) for sat in args]
        except TleNotFound:
            print("Unknwon satellite '{}'".format(" ".join(args)), file=sys.stderr)
            sys.exit(-1)
    elif stdin and not sys.stdin.isatty():
        stdin = sys.stdin.read()

        try:
            sats = Satellite.parse(stdin)
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(-1)

        if not sats:
            print("No orbit provided, data in stdin was:\n", file=sys.stderr)
            print(indent(stdin, "   "), file=sys.stderr)
            sys.exit(-1)
    else:
        print("No orbit provided", file=sys.stderr)
        sys.exit(-1)

    return sats


class Satellite:

    def __init__(self, name, **kwargs):

        self.name = name
        self.norad_id = kwargs.get('norad_id')
        self.cospar_id = kwargs.get('cospar_id')
        self.tle = kwargs.get('tle')
        self.orb = kwargs.get('orb')

    def __repr__(self):
        return "<Satellite '%s'>" % self.name

    @classmethod
    def from_tle(cls, tle):
        return cls(
            name=tle.name,
            norad_id=tle.norad_id,
            cospar_id=tle.cospar_id,
            orb=tle.orbit(),
            tle=tle
        )

    @classmethod
    def from_ccsds(cls, ccsds):
        return cls(
            name=ccsds.name,
            cospar_id=ccsds.cospar_id,
            orb=ccsds
        )

    @classmethod
    def parse(cls, txt):

        sats = [cls.from_tle(tle) for tle in Tle.from_string(txt)]

        if not sats:
            try:
                ccsds = loads(txt)
            except ValueError:
                raise ValueError("No valid TLE nor CCSDS")
            else:
                if isinstance(ccsds, (Ephem, Orbit)):
                    sats = [cls.from_ccsds(ccsds)]
                else:
                    sats = [cls.from_ccsds(ephem) for ephem in ccsds]

        return sats
