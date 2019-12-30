import logging
import asyncio
import aiohttp
import async_timeout
import requests
from bs4 import BeautifulSoup

from .common import TMP_FOLDER
from ..wspace import ws
from .db import TleDb

log = logging.getLogger(__name__)

TMP_FOLDER = TMP_FOLDER / "celestrak"
CELESTRAK_URL = "http://celestrak.com/NORAD/elements/"
PAGE_LIST_CONFIG = ("celestrak", "page-list")
DEFAULT_FILES = [
    "stations.txt",
    "tle-new.txt",
    "visual.txt",
    "weather.txt",
    "noaa.txt",
    "goes.txt",
    "resource.txt",
    "sarsat.txt",
    "dmc.txt",
    "tdrss.txt",
    "argos.txt",
    "geo.txt",
    "intelsat.txt",
    "gorizont.txt",
    "raduga.txt",
    "molniya.txt",
    "iridium.txt",
    "orbcomm.txt",
    "globalstar.txt",
    "amateur.txt",
    "x-comm.txt",
    "other-comm.txt",
    "gps-ops.txt",
    "glo-ops.txt",
    "galileo.txt",
    "beidou.txt",
    "sbas.txt",
    "nnss.txt",
    "musson.txt",
    "science.txt",
    "geodetic.txt",
    "engineering.txt",
    "education.txt",
    "military.txt",
    "radar.txt",
    "cubesat.txt",
    "other.txt",
    "active.txt",
    "analyst.txt",
    "planet.txt",
    "spire.txt",
    "ses.txt",
    "iridium-NEXT.txt",
]


def fetch(files=None):
    """Main function to retrieve celestrak pages

    Args:
        files (List[str]) : List of files to download
            if ``None`, all pages are downloaded
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_fetch(files))


def fetch_list():
    """Retrieve list of available celestrak files
    """

    log.info("Retrieving list of available celestrak files")

    log.debug("Downloading from %s", CELESTRAK_URL)
    page = requests.get(CELESTRAK_URL)

    files = []
    bs = BeautifulSoup(page.text, features="lxml")
    for link in bs.body.find_all("a"):
        if "href" in link.attrs and link["href"].endswith(".txt"):
            files.append(link.get("href"))

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
        async with session.get(CELESTRAK_URL + filename) as response:
            text = await response.text()

            filepath = TMP_FOLDER / filename

            if not TMP_FOLDER.exists():
                TMP_FOLDER.mkdir(parents=True)

            with filepath.open("w") as fp:
                fp.write(text)

            TleDb().insert(text, filename)


async def _fetch(files=None):
    """Retrieve TLE from the celestrak.com website asynchronously
    """

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
