import logging
import requests

from .db import TleDb
from .common import TMP_FOLDER
from ..wspace import ws

SPACETRACK_URL_AUTH = "https://www.space-track.org/ajaxauth/login"
SPACETRACK_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/{mode}/{selector}/orderby/ORDINAL%20asc/limit/1/format/3le/emptyresult/show"
log = logging.getLogger(__name__)


def fetch(*sats):

    try:
        auth = ws.config["spacetrack"]
    except KeyError:
        raise ValueError("No login information available for spacetrack")

    _conv = {
        "norad_id": "NORAD_CAT_ID",
        "cospar_id": "INTLDES",
        "name": "OBJECT_NAME",
    }

    log.debug("Authentication to Space-Track website")
    init = requests.post(SPACETRACK_URL_AUTH, auth)

    try:
        init.raise_for_status()
    except requests.exceptions.HTTPError as e:
        log.error("Authentication failed")
        log.exception(e)
        raise

    if init.text != '""':
        log.error("Authentication failed")
        log.debug("Response from authentication page '%s'", init.text)
        return

    log.debug("Authorized to proceed")

    text = ""
    for sat in sats:
        key = next(iter(sat.keys()))

        if key == "cospar_id":
            # The COSPAR ID should be formated as in TLE
            # i.e. "2019-097A" becomes "19097A"
            sat[key] = sat[key][2:].replace("-", "")

        url = SPACETRACK_URL.format(mode=_conv[key], selector=sat[key])

        log.debug("Request at %s", url)
        full = requests.get(url, cookies=init.cookies)

        try:
            full.raise_for_status()
        except Exception as e:
            log.error(e)
        else:
            text += full.text

    cache = TMP_FOLDER / "spacetrack.txt"
    log.debug("Caching results into %s", cache)
    with cache.open("w") as fp:
        fp.write(text)

    TleDb().insert(text, "spacetrack.txt")
