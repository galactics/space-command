
from beyond.dates import Date as LegacyDate, timedelta

from space.config import config


class Date(LegacyDate):

    CONFIG_FIELD = "clock-offset"

    @classmethod
    def _clock_offset(cls):
        return timedelta(seconds=config.get(cls.CONFIG_FIELD, fallback=0))

    @classmethod
    def now(cls, *args, **kwargs):
        return cls(super().now(*args, **kwargs) + cls._clock_offset())


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
        <date>      New date to set
        <ref>       Date at witch the new date is set. If absent, the current
                    system time is used
        <offset>    Offset
    """

    from space.utils import docopt

    args = docopt(space_clock.__doc__, options_first=True)
    # print(args)

    if args['sync']:
        config.set(Date.CONFIG_FIELD, 0)
        print("Clock set to system time")
    elif args['set-date']:
        if args['<ref>'] is None:
            now = LegacyDate.now()
        else:
            now = LegacyDate.strptime(args['<ref>'], "%Y-%m-%dT%H:%M:%S")
        date = LegacyDate.strptime(args['<date>'], "%Y-%m-%dT%H:%M:%S")
        offset = date - now - timedelta(seconds=date._offset - now._offset)
        config.set(Date.CONFIG_FIELD, offset.total_seconds())
        print("Clock set to {} (offset {})".format(date, offset))
        print()
    elif args['set-offset']:
        offset = float(args['<offset>'])
        config.set(Date.CONFIG_FIELD, offset)

        print("Clock offset set to {} seconds".format(offset))
        print()


    now = Date.now()
    print("System Date : {}".format(now - Date._clock_offset()))
    print("Clock Date  : {}".format(now))
    print("Offset      : {}".format(now._clock_offset()))