#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import signal
import asyncio
import aiohttp
import requests
from pathlib import Path

from beyond.config import config
from beyond.dates.eop import EnvError, get_db


def fetch_sync(filelist, dst):
    """Sequential retrieval of data
    """
    for f in filelist:
        filepath = dst / Path(f).name
        print(filepath.name)
        with filepath.open('w') as fh:
            fh.write(requests.get(f).text)


async def fetch_async(session, address, dst):
    """Coroutine ro retrieve file asynchronously
    """
    filepath = dst / Path(address).name
    # with aiohttp.Timeout(10):
    async with session.get(str(address)) as response:
        with open(str(filepath), 'w') as fh:
            fh.write(await response.text())
    print(filepath.name, 'downloaded')


def space_env(*argv):
    """Retrieve environement data

    Namely, pole orientation and time-scales differences

    Usage:
        space-env
        space-env get [--sync] [--all|--daily]
        space-env insert <folder> [--all|--daily]

    Options:
        get             Retrieve available data
        --sync          Retrieve data sequentially instead of asynchronously
        insert          Insert local data into the database
        <folder>        Folder where all data are available
        --all, --daily  Force the kind of file that will be retrieved/inserted

    Without argument the command shows the current status of local data
    For more informations about environment data, check the doc
    """

    from docopt import docopt
    from textwrap import dedent
    from beyond.dates import Date

    default_kind = "daily"

    args = docopt(dedent("    " + space_env.__doc__), argv=argv)
    env_folder = config['env']['folder'] / "tmp" / "env"

    if not args['get'] and not args['insert']:

        try:
            date = Date.now().mjd
            leap_past, leap_next = get_db().get_framing_leap_seconds(date)
            range_start, range_stop = get_db().get_range()
        except EnvError as e:
            raise
            print(str(e))
            sys.exit(-1)

        print("database file     {}".format(get_db().path))
        # print("Last update:      {:%Y-%m-%d %H:%M}".format(update))
        print("Last leap-second  {:%Y-%m-%d}, TAI-UTC = {}s".format(
            Date(leap_past[0]), leap_past[1]
        ))

        if leap_next == (None, None):
            print("Next leap-second  Unknown")
        else:
            print("Next leap-second  {:%Y-%m-%d}, TAI-UTC = {}s".format(
                Date(leap_next[0]), leap_next[1]
            ))

        finals_mode = config.get('eop', 'source', fallback=default_kind)
        print("Finals mode       {}".format(finals_mode))
        print("Finals range      {:%Y-%m-%d} to {:%Y-%m-%d}".format(
            Date(range_start),
            Date(range_stop),
        ))
        print("")
    else:

        # Force the kind of data to retrieve/read locally
        if args["--all"]:
            kind = "all"
        elif args['--daily']:
            kind = "daily"
        else:
            kind = config.get('eop', 'source', fallback=default_kind)

        tai_utc = "tai-utc.dat"
        finals = "finals.%s" % kind
        finals2000a = "finals2000A.%s" % kind

        if args['get']:
            baseurl = "http://maia.usno.navy.mil/ser7/%s"

            filelist = [
                baseurl % tai_utc,
                baseurl % finals,
                baseurl % finals2000a,
            ]

            if not env_folder.exists():
                env_folder.mkdir(parents=True)

            if args['--sync']:
                fetch_sync(filelist, env_folder)
            else:
                loop = asyncio.get_event_loop()

                with aiohttp.ClientSession(loop=loop) as session:

                    def signal_handler(signal, frame):
                        """Interuption handling
                        """
                        loop.stop()
                        session.close()
                        sys.exit(0)

                    signal.signal(signal.SIGINT, signal_handler)

                    tasks = []
                    for p in filelist:
                        tasks.append(asyncio.ensure_future(
                            fetch_async(session, p, env_folder)
                        ))

                    loop.run_until_complete(asyncio.wait(tasks))
                    loop.stop()

        elif args['insert']:
            # Insert local data
            env_folder = Path(args['<folder>'])

        try:
            get_db().insert(
                finals=env_folder / finals,
                finals2000a=env_folder / finals2000a,
                tai_utc=env_folder / tai_utc
            )
        except FileNotFoundError as e:
            print(e.strerror, ":", e.filename)
            sys.exit(-1)

        print("Env updated with '{}' data".format(kind))
