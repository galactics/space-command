import math
import warnings
from pathlib import Path
from peewee import Model, IntegerField, SqliteDatabase, FloatField, fn

from beyond.config import config as bconfig
from beyond.utils.memoize import memoize

from beyond.dates.eop import (
    register, Finals2000A, Finals, TaiUtc, Eop, EnvError, policy
)

__version__ = "0.2"


@register
class EnvDatabase:
    """Database storing and providing data for Earth Orientation Parameters
    and Timescales differences.

    It uses sqlite3 as engine.
    """

    db = SqliteDatabase(None)

    PASS = "pass"
    EXTRA = "extrapolate"
    WARN = "warning"
    ERROR = "error"

    MIS_DEFAULT = ERROR
    """Default behaviour in case of missing value, see :ref:`configuration <eop-missing-policy>`."""

    def __init__(self):
        self.path = bconfig.get('env', "folder", fallback=Path.cwd()) / "space.db"
        self.db.init(str(self.path))
        self.db.create_tables([FinalsModel, TaiUtcModel], safe=True)

    @memoize
    def __getitem__(self, mjd: float):

        if isinstance(mjd, int) or mjd.is_integer():
            data = self._get_finals(int(mjd)).copy()
        else:
            mjd0 = int(math.floor(mjd))
            mjd1 = int(math.ceil(mjd))
            data_start = self._get_finals(mjd0)
            data_stop = self._get_finals(mjd1)

            data = {}
            for field in data_start.keys():
                y0 = data_start[field]
                y1 = data_stop[field]
                data[field] = y0 + (y1 - y0) * (mjd - mjd0) / (mjd1 - mjd0)

        data['tai_utc'] = self._get_tai_utc(int(mjd))

        return Eop(**data)

    @memoize
    def _get_finals(self, mjd: int):

        query = FinalsModel.select().where(FinalsModel.mjd == mjd)

        try:
            data = query.get()
        except FinalsModel.DoesNotExist as e:
            # In the case of a missing value, we take the last available
            if policy() in (self.WARN, self.EXTRA):
                query = FinalsModel.select().where(FinalsModel.mjd <= mjd).order_by(FinalsModel.mjd.desc()).limit(1)

                try:
                    data = query.get()
                except FinalsModel.DoesNotExist as e:
                    raise KeyError(mjd) from e
                else:
                    if policy() == self.WARN:
                        warnings.warn("Missing EOP data. Extrapolating from previous")

            else:
                raise KeyError(mjd) from e

        return data.as_dict()

    @memoize
    def _get_tai_utc(self, mjd: int):
        query = TaiUtcModel.select().where(TaiUtcModel.mjd <= mjd)

        try:
            data = query.get()
        except TaiUtcModel.DoesNotExist as e:
            raise KeyError(mjd) from e

        # only return the tai-utc data, not the mjd
        return data.tai_utc

    @classmethod
    def get_range(cls):
        """Get the first and last date available for Earth Orientation Parameters

        Return:
            tuple
        """
        query = FinalsModel.select(fn.Min(FinalsModel.mjd), fn.Max(FinalsModel.mjd))

        try:
            data = query.scalar(as_tuple=True)
        except FinalsModel.DoesNotExist:
            raise EnvError("No data for range")

        return data

    @classmethod
    def get_framing_leap_seconds(cls, mjd: float):
        """
        Args:
            mjd (float):
        Return:
            tuple: previous and next leap second relative to mjd

        If no data is available, return None
        """
        data = TaiUtcModel.select().order_by(TaiUtcModel.mjd.desc())

        l, n = (None, None), (None, None)

        for entity in data:
            if entity.mjd <= mjd:
                l = (entity.mjd, entity.tai_utc)
                break
            n = (entity.mjd, entity.tai_utc)

        return l, n

    @classmethod
    def insert(cls, *, finals=None, finals2000a=None, tai_utc=None):
        """Insert values extracted from Finals, Finals2000A and tai-utc files
        into the environment database

        Keyword Args:
            finals (str): Path to the `finals`
            finals2000A (str): Path to the `finals2000A`
            tai_utc (str): Path to the `tai-utc.dat`

        For `finals` and `finals2000A` files, extension can be 'daily', 'data', 'all'
        depending on the freshness and the range of the data desired by
        the user.
        """

        self = cls()

        if None in (finals, finals2000a, tai_utc):
            raise TypeError("All three arguments are required")

        finals = Finals(finals)
        finals2000a = Finals2000A(finals2000a)
        tai_utc = TaiUtc(tai_utc)

        data = {}
        for date in finals.data.keys():
            data[date] = finals.data[date].copy()
            data[date].update(finals2000a.data[date])

        self._insert_eops(data)
        self._insert_tai_utc(tai_utc.data)

    def _insert_eops(self, eops: dict):
        """Insert EOP values into the database, for later use

        Prime sources for these values are :py:class:`Finals` and
        :py:class:`Finals2000A` files

        Args:
            eops (dict): The keys are the date of the value in MJD (int) and the
                values are dictionaries containing the x, y, dx, dy, deps, dpsi,
                lod and ut1_utc data
        """
        with self.db.atomic():
            FinalsModel.insert_many(eops.values()).execute()

    def _insert_tai_utc(self, tai_utcs: list):
        """Insert TAI-UTC values into the database
        """

        with self.db.atomic():
            for mjd, tai_utc in tai_utcs:
                TaiUtcModel.create(mjd=mjd, tai_utc=tai_utc)


class FinalsModel(Model):

    mjd = IntegerField()
    x = FloatField()
    y = FloatField()
    dx = FloatField()
    dy = FloatField()
    dpsi = FloatField()
    deps = FloatField()
    lod = FloatField()
    ut1_utc = FloatField()

    class Meta:
        database = EnvDatabase.db

    def as_dict(self):
        return {
            "x": self.x, "y": self.y, "dx": self.dx, "dy": self.dy,
            "deps": self.deps, "dpsi": self.dpsi, "lod": self.lod,
            "ut1_utc": self.ut1_utc,
        }


class TaiUtcModel(Model):
    mjd = IntegerField()
    tai_utc = IntegerField()

    class Meta:
        database = EnvDatabase.db
