import os
import logging
from datetime import datetime
import numpy as np
from peewee import (
    Model,
    IntegerField,
    CharField,
    TextField,
    DateTimeField,
    SqliteDatabase,
    fn,
)
import matplotlib.pyplot as plt

from beyond.io.tle import Tle
from beyond.dates import Date, timedelta

from ..wspace import ws

log = logging.getLogger(__name__)


class TleNotFound(Exception):
    def __init__(self, selector, mode=None):
        self.selector = selector
        self.mode = mode

    def __str__(self):
        if self.mode:
            return "No TLE for {obj.mode} = '{obj.selector}'".format(obj=self)

        return "No TLE containing '{}'".format(self.selector)


class TleDb:

    db = SqliteDatabase(None)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):

        self._cache = {}
        self.model = TleModel
        self.db.init(str(ws.folder / "space.db"))
        self.model.create_table(safe=True)

    def dump(self, all=False):

        bd_request = self.model.select().order_by(self.model.norad_id, self.model.epoch)

        if not all:
            bd_request = bd_request.group_by(self.model.norad_id)

        for tle in bd_request:
            yield Tle("%s\n%s" % (tle.name, tle.data), src=tle.src)

    @classmethod
    def get(cls, **kwargs):
        """Retrieve one TLE from the table from one of the available fields

        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
        Return:
            Tle:
        """
        entity = cls()._get_last_raw(**kwargs)
        return Tle("%s\n%s" % (entity.name, entity.data), src=entity.src)

    def _get_last_raw(self, **kwargs):
        """
        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
        Return:
            TleModel:
        """

        try:
            return (
                self.model.select()
                .filter(**kwargs)
                .order_by(self.model.epoch.desc())
                .get()
            )
        except TleModel.DoesNotExist as e:
            mode, selector = kwargs.popitem()
            raise TleNotFound(selector, mode=mode) from e

    @classmethod
    def get_dated(cls, limit=None, date=None, **kwargs):

        self = cls()

        if limit == "after":
            r = (
                self.model.select()
                .where(self.model.epoch >= date)
                .order_by(self.model.epoch.asc())
            )
        else:
            r = (
                self.model.select()
                .where(self.model.epoch <= date)
                .order_by(self.model.epoch.desc())
            )

        try:
            entity = r.filter(**kwargs).get()
        except self.model.DoesNotExist:
            mode, selector = kwargs.popitem()
            raise TleNotFound(selector, mode=mode) from e
        else:
            return Tle("%s\n%s" % (entity.name, entity.data), src=entity.src)

    def history(self, *, number=None, start=None, stop=None, **kwargs):
        """Retrieve all the TLE of a given object

        Keyword Arguments:
            norad_id (int)
            cospar_id (str)
            name (str)
            number (int): Number of TLE to retrieve (unlimited if None)
            start (Date): Beginning of the range (- infinity if None)
            stop (Date):  End of the range (now if None)
        Yield:
            TleModel:
        """

        query = self.model.select().filter(**kwargs).order_by(self.model.epoch)

        if start:
            query = query.where(self.model.epoch >= start.datetime)
        if stop:
            query = query.where(self.model.epoch <= stop.datetime)

        if not query:
            mode, selector = kwargs.popitem()
            raise TleNotFound(selector, mode=mode)

        number = 0 if number is None else number

        for el in query[-number:]:
            yield Tle("%s\n%s" % (el.name, el.data), src=el.src)

    def load(self, filepath):
        """Insert the TLEs contained in a file in the database
        """
        with open(filepath) as fh:
            self.insert(fh.read(), os.path.basename(filepath))

    def insert(self, tles, src=None):
        """
        Args:
            tles (str or List[Tle]): text containing the TLEs
            src (str): Where those TLEs come from
        Return:
            2-tuple: Number of tle inserted, total tle found in the text
        """

        if isinstance(tles, str):
            tles = Tle.from_string(tles)

        with self.db.atomic():
            entities = []
            i = None
            for i, tle in enumerate(tles):
                try:
                    # An entry in the table correponding to this TLE has been
                    # found, there is no need to update it
                    entity = self.model.get(
                        self.model.norad_id == tle.norad_id,
                        self.model.epoch == tle.epoch.datetime,
                    )
                    continue
                except TleModel.DoesNotExist:
                    # This TLE is not registered yet, lets go !
                    entity = {
                        "norad_id": int(tle.norad_id),
                        "cospar_id": tle.cospar_id,
                        "name": tle.name,
                        "data": tle.text,
                        "epoch": tle.epoch.datetime,
                        "src": src,
                        "insert_date": datetime.now(),
                    }
                    entities.append(entity)

            if entities:
                TleModel.insert_many(entities).execute()
            elif i is None:
                raise ValueError("{} contains no TLE".format(src))

        log.info("{}  {:>3}/{}".format(src, len(entities), i + 1))

    def find(self, txt):
        """Retrieve every TLE containing a string. For each object, only get the
        last TLE in database

        Args:
            txt (str)
        Return:
            Tle:
        """

        entities = (
            self.model.select()
            .where(self.model.data.contains(txt) | self.model.name.contains(txt))
            .order_by(self.model.norad_id, self.model.epoch.desc())
            .group_by(self.model.norad_id)
        )

        sats = []
        for entity in entities:
            sats.append(Tle("%s\n%s" % (entity.name, entity.data), src=entity.src))
        if not sats:
            raise TleNotFound(txt)

        return sats

    def print_stats(self, graph=False):

        first = self.model.select(fn.MIN(TleModel.insert_date)).scalar()
        last = self.model.select(fn.MAX(TleModel.insert_date)).scalar()
        objects_nb = self.model.select().group_by(TleModel.norad_id).count()
        tles_nb = self.model.select().count()

        ages = []
        now = Date.now()
        for tle in self.model.select().group_by(self.model.norad_id):
            ages.append((now - tle.epoch).total_seconds() / 86400)

        print(f"Objects      : {objects_nb}")
        print(f"TLE          : {tles_nb}")
        print(f"First fetch  : {first:%F %T} ({now.datetime - first} ago)")
        print(f"Last fetch   : {last:%F %T} ({now.datetime - last} ago)")
        print(f"Median age   : {timedelta(np.median(ages))} (last TLE for each object)")

        if graph:
            plt.figure()
            plt.hist(ages, range(30), rwidth=0.9)
            plt.grid(linestyle=":", color="#666666")
            plt.title("Repartition of the last available TLE for each object")
            plt.gca().set_yscale("log")
            plt.xlabel("days")
            plt.ylabel("number")
            plt.tight_layout()
            plt.show()


class TleModel(Model):
    """Peewee description of the database structure for storing TLEs
    """

    norad_id = IntegerField()
    cospar_id = CharField()
    name = CharField()
    data = TextField()
    epoch = DateTimeField()
    src = TextField()
    insert_date = DateTimeField()

    class Meta:
        database = TleDb.db


TleModel.add_index(TleModel.norad_id.desc(), TleModel.epoch.desc(), unique=True)
