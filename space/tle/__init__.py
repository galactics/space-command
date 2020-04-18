"""This package handle retrieval and archive of TLEs
"""

import sys
import logging
from glob import glob

from ..wspace import ws
from ..utils import docopt
from ..sat import Sat, Request, sync
from .db import TleDb, TleNotFound
from . import celestrak
from . import spacetrack

log = logging.getLogger(__name__)


def wshook(cmd, *args, **kwargs):
    """Workspace hook

    will be executed during worspace creation or status check
    """

    if cmd == "full-init":
        try:
            TleDb.get(norad_id=25544)
        except TleNotFound:
            celestrak.fetch()
            log.info("TLE database initialized")
        else:
            log.info("TLE database already exists")
    elif cmd == "status":
        print()
        print("TLE")
        print("---")
        TleDb().print_stats()


def space_tle(*argv):
    """TLE Database from Space-Track and Celestrak websites

    Usage:
      space-tle get <selector>...
      space-tle find <text> ...
      space-tle history [--last <nb>] <selector>...
      space-tle stats [--graph]
      space-tle dump [--all]
      space-tle insert (-|<file>...)
      space-tle celestrak fetch [<file>...]
      space-tle celestrak fetch-list
      space-tle spacetrack fetch <selector>...

    Options:
      get              Display the last TLE of a selected object
      find             Search for a string in the database of TLE (case insensitive)
      history          Display all the recorded TLEs for a given object
      stats            Display statistics on the database
      dump             Display the last TLE for each object
      insert           Insert TLEs into the database (from file or stdin)
      celestrak
        fetch          Retrieve TLEs from Celestrak website
        fetch-list     Retrieve the list of available files from Celestrak
      spacetrack
        fetch          Retrieve a single TLE per object from the Space-Track
                       website. This request needs login informations (see below)
      <selector>       Selector of the object, see `space sat`
      <file>           File to insert in the database
      -l, --last <nb>  Get the last <nb> TLE
      -a, --all        Display the entirety of the database, instead of only
                       the last TLE of each object
      -g, --graph      Display statistics graphically

    Examples:
      space tle celestrak fetch              # Retrieve all the TLEs from celestrak
      space tle celestrak fetch visual.txt   # Retrieve a single file from celestrak
      space tle spacetrack fetch norad=25544 # Retrieve a single TLE from spacetrack
      space tle get norad=25544              # Display the TLE of the ISS
      space tle get cospar=1998-067A         # Display the TLE of the ISS, too
      space tle insert file.txt              # Insert all TLEs from the file
      echo "..." | space tle insert          # Insert TLEs from stdin

    Configuration:
      The Space-Track website only allows TLE downloads from logged-in requests.
      To do this, the config file should contain
          spacetrack:
              identity: <login>
              password: <password>

      Every time you retrieve or insert TLE in the database, the satellite database
      is updated. To disable this behaviour add the following to the config file
          satellites:
              auto-sync-tle: False
    """

    args = docopt(space_tle.__doc__, argv=argv)

    db = TleDb()

    if args["celestrak"]:

        if args["fetch"]:
            log.info("Retrieving TLEs from celestrak")

            try:
                celestrak.fetch(*args["<file>"])
            except ValueError as e:
                log.error(e)
            finally:
                if ws.config.get("satellites", "auto-sync-tle", fallback=True):
                    # Update the Satellite DB
                    sync("tle")
        elif args["fetch-list"]:
            celestrak.fetch_list()
    elif args["spacetrack"] and args["fetch"]:
        log.info("Retrieving TLEs from spacetrack")

        sats = []

        for sel in args["<selector>"]:
            desc = Request.from_text(sel)
            sats.append({desc.selector: desc.value})

        try:
            spacetrack.fetch(*sats)
        except ValueError as e:
            log.error(e)
        finally:
            if ws.config.get("satellites", "auto-sync-tle", fallback=True):
                # Update the Satellite DB
                sync("tle")
    elif args["insert"]:
        # Process the file list provided by the command line
        if args["<file>"]:
            files = []
            for f in args["<file>"]:
                files.extend(glob(f))

            # Insert each file into the database
            for file in files:
                try:
                    db.load(file)
                except Exception as e:
                    log.error(e)

        elif args["-"] and not sys.stdin.isatty():
            try:
                # Insert the content of stdin into the database
                db.insert(sys.stdin.read(), "stdin")
            except Exception as e:
                log.error(e)
        else:
            log.error("No TLE provided")
            sys.exit(1)

        if ws.config.get("satellites", "auto-sync-tle", fallback=True):
            # Update the Satellite DB
            sync()

    elif args["find"]:
        txt = " ".join(args["<text>"])
        try:
            result = db.find(txt)
        except TleNotFound as e:
            log.error(str(e))
            sys.exit(1)

        for tle in result:
            print("{0.name}\n{0}\n".format(tle))

        log.info("==> %d entries found for '%s'", len(result), txt)
    elif args["dump"]:
        for tle in db.dump(all=args["--all"]):
            print("{0.name}\n{0}\n".format(tle))
    elif args["stats"]:
        db.print_stats(args["--graph"])
    else:
        try:
            sats = list(Sat.from_selectors(*args["<selector>"], src="tle"))
        except ValueError as e:
            log.error(str(e))
            sys.exit(1)

        for sat in sats:
            try:
                if args["history"]:
                    number = int(args["--last"]) if args["--last"] is not None else None
                    tles = db.history(number=number, cospar_id=sat.cospar_id)

                    for tle in tles:
                        print("{0.name}\n{0}\n".format(tle))
                else:
                    print("{0.name}\n{0}\n".format(sat.orb.tle))
            except TleNotFound as e:
                log.error(str(e))
                sys.exit(1)
