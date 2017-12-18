
from beyond.orbits import Tle


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
    def parse(cls, txt):
        sats = [cls.from_tle(tle) for tle in Tle.from_string(txt)]
        if not sats:
            raise ValueError("No TLE")

        return sats
