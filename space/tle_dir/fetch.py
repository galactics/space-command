from datetime import datetime

from peewee import IntegrityError
from spacetrack import SpaceTrackClient
import spacetrack.operators as op

from space.wspace import ws


def fetch_st_historic(insert_fn, argv):
    # example usage:
    # fetch_st_historic(intert_fn, ["xx", 25544, ">now-2"])

    norad_id = int(argv[1])
    epoch_str = argv[2]

    creds= ws.config["spacetrack"]
    st = SpaceTrackClient(creds['username'], creds['password'])

    tles = st.tle(norad_cat_id=norad_id,
                  iter_lines=True,
                  epoch=epoch_str,
                  orderby='epoch desc',
                  format='tle')

    s = ''
    for line1 in tles:
        line2 = next(tles)
        s += '{}\n{}\n'.format(line1, line2)

    insert_fn(s, 'spacetrack.txt')
