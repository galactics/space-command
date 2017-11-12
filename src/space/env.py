#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import signal
import asyncio
import aiohttp
import requests

from pathlib import Path

from beyond.config import config


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
    print("start", filepath)
    async with session.get(address) as response:
        with open(str(filepath), 'w') as fh:
            fh.write(await response.text())
    print("finished", filepath)


def space_env(*argv):
    """\
    Retrieve environement data

    Namely, pole motion and time-scales differences

    Usage:
        space-env
        space-env get [--sync]

    Options:
        get     Retrieve available data
        --sync  Retrieve data sequentially instead of asynchronously

    Without argument the command shows the current status of local data
    For more informations about environment data, check the doc
    """

    from docopt import docopt
    from textwrap import dedent

    args = docopt(dedent(space_env.__doc__), argv=argv)
    env_folder = config['folder'] / "env"

    if not args['get']:
        from datetime import datetime
        from beyond.env.poleandtimes import TaiUtc, Finals
        from beyond.utils import Date

        date = Date.now().mjd
        past, future = TaiUtc().get_last_next(date)

        timestamp = (env_folder / 'tai-utc.dat').stat().st_mtime
        update = datetime.fromtimestamp(timestamp)

        print("Last update:      {:%Y-%m-%d %H:%M}".format(update))

        print("Last leap-second: {:%Y-%m-%d}, TAI-UTC = {}s".format(
            Date(past[0]), past[1]
        ))

        if future == (None, None):
            print("Next leap-second: Unknown")
        else:
            print("Next leap-second: {:%Y-%m-%d}, TAI-UTC = {}s".format(
                Date(future[0]), future[1]
            ))

        final = Finals()
        print("Finals mode:      {}".format(final.path.suffix[1:]))
        print("Finals range:     {:%Y-%m-%d} to {:%Y-%m-%d}".format(
            Date(min(final.data.keys())),
            Date(max(final.data.keys())),
        ))
        print("")
    else:

        baseurl = "http://maia.usno.navy.mil/ser7/"

        filelist = [
            baseurl + 'tai-utc.dat',
        ]

        if config['env']['eop_source'] == "all":
            filelist.extend([
                baseurl + 'finals2000A.all',
                baseurl + 'finals.all',
            ])
        else:
            filelist.extend([
                baseurl + 'finals2000A.daily',
                baseurl + 'finals.daily',
            ])

        if not env_folder.exists():
            env_folder.mkdir()

        if args['--sync']:
            fetch_sync(filelist, env_folder)
        else:
            loop = asyncio.get_event_loop()

            with aiohttp.ClientSession(loop=loop) as session:

                def signal_handler(signal, frame):
                    """Gestion de l'interruption du programme
                    """
                    loop.stop()
                    session.close()
                    sys.exit(0)

                signal.signal(signal.SIGINT, signal_handler)

                # Crétion de la liste des tâches
                tasks = [asyncio.ensure_future(fetch_async(session, p, env_folder)) for p in filelist]

                # Déclenchement des tâches (asyncio.wait()) et ajout à la boucle
                # d'évènements.
                loop.run_until_complete(asyncio.wait(tasks))
                loop.stop()
                session.close()
