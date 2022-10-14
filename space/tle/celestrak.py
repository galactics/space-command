import logging
import asyncio
import aiohttp
import async_timeout
import re
import requests
from bs4 import BeautifulSoup

from .common import TMP_FOLDER
from ..wspace import ws
from .db import TleDb

log = logging.getLogger(__name__)

TMP_FOLDER = TMP_FOLDER / "celestrak"
CELESTRAK_LIST = "http://celestrak.org/NORAD/elements/"
CELESTRAK_URL = "http://celestrak.org/NORAD/elements/gp.php?FORMAT=3le&GROUP={}"
PAGE_LIST_CONFIG = ("celestrak", "page-list")
DEFAULT_FILES = [
    "stations",
    "last-30-days",
    "visual",
    "weather",
    "noaa",
    "goes",
    "resource",
    "sarsat",
    "dmc",
    "tdrss",
    "argos",
    "geo",
    "intelsat",
    "gorizont",
    "raduga",
    "molniya",
    "iridium",
    "orbcomm",
    "globalstar",
    "amateur",
    "x-comm",
    "other-comm",
    "gps-ops",
    "glo-ops",
    "galileo",
    "beidou",
    "sbas",
    "nnss",
    "musson",
    "science",
    "geodetic",
    "engineering",
    "education",
    "military",
    "radar",
    "cubesat",
    "other",
    "active",
    "analyst",
    "planet",
    "spire",
    "ses",
    "iridium-NEXT",
]


def fetch(files=None):
    """Main function to retrieve celestrak pages

    Args:
        files (List[str]) : List of files to download
            if ``None`, all pages are downloaded
    """
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(_fetch(files))
    except aiohttp.ClientError as e:
        log.error(e)


def fetch_list():
    """Retrieve list of available celestrak files"""

    log.info("Retrieving list of available celestrak files")

    log.debug("Downloading from %s", CELESTRAK_LIST)
    page = requests.get(CELESTRAK_LIST)

    files = []
    bs = BeautifulSoup(page.text, features="lxml")
    for link in bs.body.find_all("a"):
        if "href" in link.attrs:
            linkmatch = re.fullmatch(
                r"gp\.php\?GROUP=([A-Za-z0-9\-]+)&FORMAT=tle", link["href"]
            )
            if linkmatch is not None:
                files.append(linkmatch.group(1) + "")

    log.info("%d celestrak files found", len(files))

    if not TMP_FOLDER.exists():
        TMP_FOLDER.mkdir(parents=True)

    celestrak_pages = ws.config.get(*PAGE_LIST_CONFIG, fallback=DEFAULT_FILES)

    for p in set(celestrak_pages).difference(files):
        log.debug("Removing '%s' from the list of authorized celestrak pages", p)

    for p in set(files).difference(celestrak_pages):
        log.debug("Adding '%s' to the list of authorized celestrak pages", p)

    ws.config.set(*PAGE_LIST_CONFIG, files, save=True)


async def _fetch_file(session, filename):
    """Coroutine to retrieve the specified page

    When the page is totally retrieved, the function will call insert
    """
    with async_timeout.timeout(30):
        async with session.get(CELESTRAK_URL.format(filename)) as response:
            text = await response.text()

            filepath = TMP_FOLDER / filename

            if not TMP_FOLDER.exists():
                TMP_FOLDER.mkdir(parents=True)

            with filepath.open("w") as fp:
                fp.write(text)

            TleDb().insert(text, filename)


async def _fetch(files=None):
    """Retrieve TLE from the celestrak.com website asynchronously"""

    celestrak_pages = ws.config.get(*PAGE_LIST_CONFIG, fallback=DEFAULT_FILES)

    if files is None:
        filelist = celestrak_pages
    else:
        if isinstance(files, str):
            files = [files]
        # Filter out file not included in the base list
        files = set(files)
        filelist = files.intersection(celestrak_pages)
        remaining = files.difference(celestrak_pages)

        for p in remaining:
            log.warning("Unknown celestrak pages '%s'", p)

        if not filelist:
            raise ValueError("No file to download")

    async with aiohttp.ClientSession(trust_env=True) as session:

        # Task list initialisation
        tasks = [_fetch_file(session, f) for f in filelist]

        await asyncio.gather(*tasks)
