import sys
import logging

from beyond.dates import Date as LegacyDate, timedelta

from .wspace import ws
from .utils import parse_timedelta


log = logging.getLogger(__name__)


class Date(LegacyDate):

    CONFIG_FIELD = "clock-offset"

    @classmethod
    def _clock_offset(cls):
        return timedelta(seconds=ws.config.get(cls.CONFIG_FIELD, fallback=0))

    @classmethod
    def now(cls, *args, **kwargs):
        return cls(super().now(*args, **kwargs) + cls._clock_offset())


def sync():
    """Synchronise the system date and the clock date
    """
    ws.config.set(Date.CONFIG_FIELD, 0, save=True)
    log.info("Clock set to system time")


def set_date(date, ref):
    """
    Args:
        date (Date)
        ref (Date)
    """

    # the timedelta is here to take the UTC-TAI into account
    # see beyond.dates.date for informations
    offset = date - ref - timedelta(seconds=date._offset - ref._offset)
    ws.config.set(Date.CONFIG_FIELD, offset.total_seconds(), save=True)
    log.info("Clock date set to {}".format(date))


def set_offset(offset):
    """
    Args
        offset (timedelta)
    """
    ws.config.set(Date.CONFIG_FIELD, offset.total_seconds(), save=True)
    log.info("Clock offset set to {}".format(offset))


def space_clock(*argv):
    """Time control

    Usage:
        space-clock
        space-clock sync
        space-clock set-date <date> [<ref>]
        space-clock set-offset <offset>

    Options:
        sync        Set the time to be the same as the system
        set-date    Define the date
        set-offset  Define offset
        <date>      New date to set (%Y-%m-%dT%H:%M:%S.%f)
        <ref>       Date at witch the new date is set (same format as <date>).
                    If absent, the current system time is used
        <offset>    Offset in seconds
    """

    from space.utils import docopt

    args = docopt(space_clock.__doc__, options_first=True)

    if args["sync"]:
        sync()
        print(file=sys.stderr)
    elif args["set-date"]:
        if args["<ref>"] is None:
            ref = LegacyDate.now()
        else:
            ref = LegacyDate.strptime(args["<ref>"], "%Y-%m-%dT%H:%M:%S.%f")
        date = LegacyDate.strptime(args["<date>"], "%Y-%m-%dT%H:%M:%S.%f")

        set_date(date, ref)

        print(file=sys.stderr)
    elif args["set-offset"]:
        offset = parse_timedelta(args["<offset>"], negative=True)
        set_offset(offset)
        print(file=sys.stderr)

    now = Date.now()
    print("System Date : {}".format(now - Date._clock_offset()))
    print("Clock Date  : {}".format(now))
    print("Offset      : {}".format(now._clock_offset()))
