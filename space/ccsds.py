"""This module provides a unified interface for CCSDS file handling

This module is not meant to be used directly. Instead use the module `space.sat`
"""

import sys
import logging
import yaml

from beyond.config import config
from beyond.io import ccsds
from beyond.orbits import Orbit, StateVector, Ephem
from beyond.propagators import get_propagator
from beyond.env.solarsystem import get_body
from beyond.dates import timedelta

from .clock import Date
from .station import StationDb
from .utils import parse_date, parse_timedelta

log = logging.getLogger(__name__)


def load(fp):
    """Convert a CCSDS file to an Orbit or Ephem instance

    .. see: :py:func:`loads`
    """
    return loads(fp.read())


def loads(text):
    """Convert a string formatted along the CCSDS standard into an Orbit or
    Ephem instance.

    This function is a wrapper of :py:func:`beyond.io.ccsds.loads` and allows
    to integrate some space-command specific fields
    """

    orb = ccsds.loads(text)

    if isinstance(orb, StateVector) and "ccsds_user_defined" in orb.complements:
        ud = orb.complements["ccsds_user_defined"]

        name = ud["PROPAGATOR"]
        if name == "KeplerNum":
            kwargs = {
                "step": timedelta(seconds=float(ud["PROPAGATOR_STEP_SECONDS"])),
                "bodies": [get_body(orb.frame.center.name)],
                "frame": orb.frame,
                "method": ud["PROPAGATOR_METHOD"],
            }
        else:
            kwargs = {}

        orb.as_orbit(get_propagator(name)(**kwargs))

    return orb


def dump(data, fp, **kwargs):
    """Convert a CCSDS file to an Orbit or Ephem instance

    .. see: :py:func:`dumps`
    """
    return fp.write(dumps(data, **kwargs))


def dumps(data, **kwargs):
    """Convert an Orbit or Ephem instance into a string formatted along the
    CCSDS standard

    This function is a wrapper of :py:func:`beyond.io.ccsds.dumps` and allows
    to integrate some space-command specific fields
    """

    if isinstance(data, Orbit):
        subdict = data.complements.setdefault("ccsds_user_defined", {})
        subdict["PROPAGATOR"] = data.propagator.__class__.__name__
        if data.propagator.__class__.__name__ == "KeplerNum":
            subdict["PROPAGATOR_STEP_SECONDS"] = "{:0.3f}".format(
                data.propagator.step.total_seconds()
            )
            subdict["PROPAGATOR_METHOD"] = data.propagator.method

    return ccsds.dumps(data, **kwargs)


class CcsdsDb:
    """CCSDS files database

    This class is not meant to be used directly. Instead use the
    :py:class:`space.sat.Sat` class.
    """

    TAG_FILE = ".tags.yml"

    @classmethod
    def _pattern(cls, ext):
        return "*.{}".format(ext)

    @classmethod
    def _tagfile(cls, sat):
        return sat.folder.joinpath(cls.TAG_FILE)

    @classmethod
    def tags(cls, sat, ext=None):
        """List existing tags for this satellite

        Args:
            sat (Sat):
            ext (str): file extension filter. If ``None``, return all
                types of files
        Return:
            dict: Key=tagname, Value=filepath
        """
        if not cls._tagfile(sat).exists():
            return {}

        data = yaml.safe_load(cls._tagfile(sat).open())
        if not data:
            return {}

        tags = {}

        for k, v in data.items():
            v = sat.folder.joinpath(v)
            if ext and v.suffix.lstrip(".") != ext:
                continue
            tags[k] = v
        return tags

    @classmethod
    def rtags(cls, sat, ext=None):
        """Reverse method of :py:meth:`tags`

        Args:
            sat (Sat):
            ext (str): file extension filter. If ``None``, return all
                types of files
        Return:
            dict: Key=filepath, Value=tags
        """
        tags = cls.tags(sat, ext)
        return dict(zip(tags.values(), tags.keys()))

    @classmethod
    def tag(cls, sat, tag, force=False):
        """Create a tag on a given Orbit or Ephem

        Args:
            sat (Sat)
            tag (str)
            force (bool)
        Raise:
            ValueError
        """
        cls._tagfile(sat).touch()

        tags = cls.tags(sat)
        if tag in list(tags.keys()):
            if not force:
                raise ValueError(
                    "The tag '{}' is already taken by {}".format(tag, tags[tag].name)
                )

            log.warning(
                "Moving tag '{}' from {} to {}".format(
                    tag, tags[tag].name, sat.orb.filepath.name
                )
            )

        tags[tag] = sat.orb.filepath
        for tag in tags:
            tags[tag] = tags[tag].name

        yaml.safe_dump(tags, cls._tagfile(sat).open("w"))

    @classmethod
    def _list(cls, sat, ext, reverse=True):
        """Iterator providing file paths
        """
        for file in sorted(sat.folder.glob(cls._pattern(ext)), reverse=reverse):
            yield file

    @classmethod
    def list(cls, sat, ext, reverse=True):
        """Iterator providing Orbit or Ephem instances
        """
        for file in cls._list(sat, ext, reverse=reverse):
            orb = load(file.open())
            orb.filepath = file
            yield orb

    @classmethod
    def insert(cls, sat, force=False):
        """Create a CCSDS file for a giver orbit

        Args:
            sat (Sat) : Satellite object, containing an orb attribute which will
                be transformed into a CCSDS file (either OEM for Ephem, or OPM
                for Orbit)
        """
        if not sat.folder.exists():
            sat.folder.mkdir(parents=True)

        if isinstance(sat.orb, Orbit):
            ext = "opm"
        elif isinstance(sat.orb, Ephem):
            ext = "oem"
        else:
            raise TypeError(
                "Unknown class for CCSDS file to insert : {}".format(type(sat.orb))
            )

        filename = cls.filename(sat, ext)
        filepath = sat.folder / filename

        if filepath.exists() and not force:
            log.error("The file {} already exists".format(filepath))
            raise FileExistsError(filepath)

        with filepath.open("w") as fp:
            dump(sat.orb, fp)

        log.info("{} saved".format(filepath))

    @classmethod
    def get(cls, sat, raw=False):
        """Retrieve a given CCSDS file

        Args:
            sat (Sat) : Sat object containing a `req` attribute describing the specific
                request
            raw (bool): If ``True``, the function returns the raw text from the file.
        Return:
            Orbit or Ephem
        """

        exception = ValueError(
            "No {} file corresponding to {}".format(sat.req.src.upper(), sat.req)
        )

        if isinstance(sat.req.date, Date):
            reverse = False
            if sat.req.limit == "before":
                func = "__lt__"
                reverse = True
            else:
                func = "__gt__"

            for file in cls._list(sat, sat.req.src, reverse):
                mtime = Date.strptime(file.stem.partition("_")[2], "%Y%m%d_%H%M%S")
                if getattr(mtime, func)(sat.req.date):
                    txt = file.open().read()
                    break
            else:
                raise exception
        else:
            for i, file in enumerate(cls._list(sat, sat.req.src)):
                if i == sat.req.offset:
                    txt = file.open().read()
                    break
            else:
                raise exception
        if raw:
            return txt
        else:
            orb = loads(txt)
            orb.filepath = file
            return orb

    @classmethod
    def filename(cls, sat, ext):
        """Method used to determine the CCSDS filename of an Orbit or Ephem object
        """
        date = sat.orb.date if ext == "opm" else sat.orb.start
        return "{sat.cospar_id}_{date:%Y%m%d_%H%M%S}.{ext}".format(
            sat=sat, ext=ext, date=date
        )


def _generic_cmd(ext, doc, *argv):  # pragma: no cover
    """Generic command handling
    """

    from .utils import docopt
    from .sat import Sat

    args = docopt(doc, argv=argv)

    if "compute" in args and args["compute"]:

        try:
            start = parse_date(args["--date"])
            if ext == "oem":
                stop = parse_timedelta(args["--range"])
                step = parse_timedelta(args["--step"])
            satlist = Sat.from_command(
                *args["<selector>"], text=sys.stdin.read() if args["-"] else ""
            )
        except ValueError as e:
            log.error(e)
            sys.exit(1)

        orbs = []
        txt = ""
        for sat in satlist:
            if ext == "oem":
                ephem = sat.orb.ephem(start=start, stop=stop, step=step)
                ephem.name = sat.name
                ephem.cospar_id = sat.cospar_id
                ephem.method = args["--interp"]
                if args["--frame"] is not None:
                    ephem.frame = StationDb.get(args["--frame"])

                orbs.append(ephem)
            else:
                orb = sat.orb.propagate(start)
                orb.name = sat.name
                orb.cospar_id = sat.cospar_id
                if args["--frame"] is not None:
                    orb.frame = StationDb.get(args["--frame"])
                if args["--propagator"]:
                    propagator_cls = get_propagator(args["--propagator"])
                    if issubclass(propagator_cls, get_propagator("KeplerNum")):
                        orb.propagator = propagator_cls(
                            parse_timedelta(args["--step"]), get_body(args["--body"])
                        )
                    else:
                        orb.propagator = propagator_cls()

                txt = dumps(
                    orb, originator=config.get("center", "name", fallback="N/A")
                )

        if ext == "oem":
            txt = dumps(orbs, originator=config.get("center", "name", fallback="N/A"))

        if not args["--insert"]:
            print(txt)

    if args["insert"] or ("compute" in args and args["compute"] and args["--insert"]):

        if args["--insert"]:
            pass
        elif args["-"] and not sys.stdin.isatty():
            txt = sys.stdin.read()
        else:
            txt = open(args["<file>"]).read()

        try:
            sats = Sat.from_command(text=txt, create=True)
        except ValueError as e:
            log.error(e)
            sys.exit(1)

        for sat in sats:
            try:
                CcsdsDb.insert(sat, args["--force"])
            except FileExistsError as e:
                continue
    elif args["list"]:

        max_idx = int(args["--last"])

        try:
            for sat in Sat.from_selectors(*args["<selector>"], src=ext, orb=False):

                print(sat.name.center(65))

                rtags = CcsdsDb.rtags(sat, ext)
                if rtags:
                    tagw = len(max(rtags.values(), key=len))
                else:
                    tagw = 4

                if ext == "oem":
                    print(
                        "idx  Tag{}  Frame     Start                Stop                 Steps".format(
                            " " * (tagw - 3)
                        )
                    )
                    print("-" * (65 + tagw))
                else:
                    print(
                        "idx  Tag{}  Frame     Date                 Propagator  Man  Cov".format(
                            " " * (tagw - 3)
                        )
                    )
                    print("-" * (65 + tagw))

                for idx, orb in enumerate(CcsdsDb.list(sat, ext)):

                    if sat.req.limit == "any" and idx == sat.req.offset:
                        color = "* \033[32m"
                        endcolor = "\033[39m"
                    else:
                        color = "  "
                        endcolor = ""

                    if idx >= max_idx:
                        break

                    if ext == "oem":
                        steps = set()
                        for orb_i, orb_j in zip(orb[:-1], orb[1:]):
                            steps.add(orb_j.date - orb_i.date)

                        if len(steps) == 1:
                            (steps,) = steps
                        elif (max(steps) - min(steps)).total_seconds() < 1e-5:
                            steps = max(steps)
                        else:
                            steps = "[{}, {}]".format(min(steps), max(steps))

                        print(
                            "{color}{idx:<2} {tag:{tagw}}  {orb.frame.name:8}  {orb.start:{fmt}}  {orb.stop:{fmt}}  {steps}{endcolor}".format(
                                idx=idx,
                                orb=orb,
                                tag=rtags[orb.filepath]
                                if orb.filepath in rtags
                                else "",
                                fmt="%Y-%m-%dT%H:%M:%S",
                                steps=steps,
                                color=color,
                                endcolor=endcolor,
                                tagw=tagw,
                            )
                        )
                    else:
                        print(
                            "{color}{idx:<2} {tag:{tagw}}  {orb.frame.name:8}  {orb.date:{fmt}}  {propagator:10}  {man}    {cov}{endcolor}".format(
                                idx=idx,
                                tag=rtags[orb.filepath]
                                if orb.filepath in rtags
                                else "",
                                orb=orb,
                                fmt="%Y-%m-%dT%H:%M:%S",
                                propagator=orb.propagator.__class__.__name__
                                if orb.propagator
                                else "None",
                                man=len(orb.maneuvers),
                                cov="Yes" if orb.cov.any() else "None",
                                color=color,
                                endcolor=endcolor,
                                tagw=tagw,
                            )
                        )

                print()
        except ValueError as e:
            log.error(e)
            sys.exit(1)

    elif args["get"]:
        ephems = []

        try:
            for sat in Sat.from_selectors(*args["<selector>"], src=ext, orb=False):
                ephem = CcsdsDb.get(sat, raw=True)
                ephems.append(ephem)
            else:
                log.error(
                    "No {} file corresponding to {}".format(
                        sat.req.src.upper(), sat.req
                    )
                )
        except ValueError as e:
            log.error(e)
            sys.exit(1)

        # print(dumps(ephems))
        print(ephems[0])
    elif args["purge"]:

        log.info("Starting deletion of {} files".format(ext.upper()))

        try:
            until = parse_timedelta(args["--until"])
        except ValueError:
            until = parse_date(args["--until"])
        else:
            until = Date.now() - until

        for sat in Sat.from_selectors(*args["<selector>"], src=ext, orb=False):

            rtags = CcsdsDb.rtags(sat)

            sublist = []
            for file in CcsdsDb._list(sat, ext):
                mtime = Date.strptime(file.stem.partition("_")[2], "%Y%m%d_%H%M%S")
                if mtime < until:
                    sublist.append(file)

            if not sublist:
                log.info("No file to delete")
                sys.exit(0)

            print("You are about to delete {} files".format(len(sublist)))
            for file in sublist:
                print("   {}".format(file.name))
            ans = input("Are you sure ? yes/[no] ")

            if ans.lower() != "yes":
                log.info("Deletion canceled")
                sys.exit(0)

            for filepath in sublist:
                if filepath in rtags:
                    log.warning(
                        "{} can't be destroyed due to the tag '{}'".format(
                            filepath.name, rtags[filepath]
                        )
                    )
                    continue
                log.debug("{} {}".format(filepath.name, "destroyed"))
                filepath.unlink()
    elif args["list-tags"]:
        for sat in Sat.from_selectors(*args["<selector>"], src=ext, orb=False):
            tags = CcsdsDb.tags(sat, ext)
            if tags:
                tagw = len(max(tags.keys(), key=len))
                for tag, filepath in tags.items():
                    print("{:{}}  {}".format(tag, tagw, filepath.name))
    elif args["tag"]:
        sat = Sat.from_selector(*args["<selector>"], src=ext)
        try:
            CcsdsDb.tag(sat, args["<tag>"], force=args["--force"])
        except ValueError as e:
            log.error(e)
            sys.exit(1)


def space_oem(*argv):
    """Handle oem files

    Usage:
        space-oem get <selector>...
        space-oem insert (- | <file>)
        space-oem compute (- | <selector>...) [options]
        space-oem list <selector>... [options]
        space-oem purge <selector>... [--until <until>]
        space-oem list-tags <selector>...
        space-oem tag <selector> <tag> [options]

    Options:
        get                   Retrieve an existing OEM from the database
        insert                Insert an OEM into the database
        compute               Compute OEM from an other OPM, OEM or TLE
        list                  List existing ephemerides
        purge                 Remove old OEMs. Use --last option
        list-tags             List available tags for ephems of the selected objects
        tag                   Create a tag for a particular ephem
        <selector>            Selector of the satellite (see help of the "sat" command)
        -f, --frame <frame>   Frame in which to write the file to
        -d, --date <date>     Start date of the ephem [default: midnight]
                              (format %Y-%m-%dT%H:%M:%S)
        -r, --range <days>    Duration of extrapolation [default: 3d]
        -s, --step <step>     Step size of the OEM [default: 180s]
        -i, --interp <inter>  Interpolation method (linear, lagrange) [default: lagrange]
        -l, --last <last>     When listing print the last N OEM [default: 10]
        -I, --insert          Insert the computed OEM into the database
        -F, --force           Force insertion
        --until <until>       When purging, remove all file older than this date [default: 4w]
                              May be a duration, or a date
    """

    return _generic_cmd("oem", space_oem.__doc__, *argv)


def space_opm(*argv):
    """Handle state vectors

    Usage:
        space-opm get <selector>...
        space-opm insert (- | <file>)
        space-opm compute (- | <selector>...) [options]
        space-opm list <selector>... [-l <last>]
        space-opm purge <selector>... [--until <until>]
        space-opm list-tags <selector>...
        space-opm tag <selector> <tag> [options]

    Options:
        get                   Retrieve an existing OPM from the database
        insert                Insert an OPM into the database
        compute               Compute a new OPM from an other OPM, OEM or TLE
        list                  List existing ephemerides
        <selector>            Selector of the satellite (see help of the "sat" command)
        -f, --frame <frame>   Frame in which to write the file to
        -d, --date <date>     Date of the new OPM [default: now]
        -p, --propagator <p>  Propagator [default: KeplerNum]
        -s, --step <step>     Step size for extrapolator [default: 60s]
        -b, --body <body>     Central body [default: Earth]
        -l, --last <last>     When listing print the last N OPMs [default: 10]
        -I, --insert          Insert the computed OPM into the database
        -F, --force           Force insertion
        --until <until>       When purging, remove all file older than this date [default: 4w]
                              May be a duration, or a date
    """

    return _generic_cmd("opm", space_opm.__doc__, *argv)
