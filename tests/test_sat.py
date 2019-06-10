from pytest import raises

from space.sat import parse_sats
from space.clock import Date


tle2 = """ISS (ZARYA)
1 25544U 98067A   17343.27310274  .00004170  00000-0  70208-4 0  9997
2 25544  51.6420 245.4915 0003135 211.8338 242.8677 15.54121086 88980

ISS (ZARYA)
1 25544U 98067A   19161.23866414  .00001034  00000-0  25191-4 0  9992
2 25544  51.6452  35.7838 0007986  32.5664 120.5149 15.51186426174176"""


def test_parse_desc(space_tmpdir):

    desc = parse_sats.get_desc("ISS (ZARYA)")

    assert desc.selector == "name"
    assert desc.value == "ISS (ZARYA)"
    assert desc.last == 0
    assert desc.src == "tle"
    # assert desc.limit == ""

    desc = parse_sats.get_desc("norad=25544~3@oem")

    assert desc.selector == "norad_id"
    assert desc.value == "25544"
    assert desc.last == 3
    assert desc.src == "oem"

    # Selection by alias
    desc = parse_sats.get_desc("ISS")

    assert desc.selector == "norad_id"
    assert desc.value == "25544"
    assert desc.last == 0
    assert desc.src == "tle"

    desc = parse_sats.get_desc("norad=25544?2019-02-27")

    assert desc.selector == "norad_id"
    assert desc.value == "25544"
    assert desc.limit == "before"
    assert desc.date == Date(2019, 2, 27)

    desc = parse_sats.get_desc("norad=25544^2019-02-27T12:00:00")

    assert desc.selector == "norad_id"
    assert desc.value == "25544"
    assert desc.limit == "after"
    assert desc.date == Date(2019, 2, 27, 12)


def test_get_sat(space_tmpdir):

    sat = parse_sats.get_sat("ISS")

    assert sat.name == "ISS (ZARYA)"
    assert sat.cospar_id == "1998-067A"
    assert sat.norad_id == 25544
    assert sat.orb == None

    with raises(ValueError):
        sat = parse_sats.get_orb("XMM")


def test_get_orb(space_tmpdir, run):

    r = run("space tle insert - ", stdin=tle2)
    assert r.success

    sat = parse_sats.get_orb("ISS")

    assert sat.name == "ISS (ZARYA)"
    assert sat.cospar_id == "1998-067A"
    assert sat.norad_id == 25544
    assert sat.orb.date == Date(2019, 6, 10, 5, 43, 40, 581696)

    sat = parse_sats.get_orb("ISS~")

    assert sat.name == "ISS (ZARYA)"
    assert sat.cospar_id == "1998-067A"
    assert sat.norad_id == 25544
    assert sat.orb.date == Date(2018, 10, 24, 13, 14, 20, 814720)

    # After the date
    sat = parse_sats.get_orb("ISS^2018-01-01")
    assert sat.orb.date == Date(2018, 10, 24, 13, 14, 20, 814720)

    # Before the date
    sat = parse_sats.get_orb("ISS?2018-01-01")
    assert sat.orb.date == Date(2017, 12, 9, 6, 33, 16, 76736)
