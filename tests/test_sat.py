from pytest import raises

from space.sat import Sat, Request
from space.clock import Date


tle2 = """ISS (ZARYA)
1 25544U 98067A   17343.27310274  .00004170  00000-0  70208-4 0  9997
2 25544  51.6420 245.4915 0003135 211.8338 242.8677 15.54121086 88980

ISS (ZARYA)
1 25544U 98067A   19161.23866414  .00001034  00000-0  25191-4 0  9992
2 25544  51.6452  35.7838 0007986  32.5664 120.5149 15.51186426174176"""


ephem = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2019-07-21T09:16:27
ORIGINATOR = N/A

META_START
OBJECT_NAME          = ISS (ZARYA)
OBJECT_ID            = 1998-067A
CENTER_NAME          = EARTH
REF_FRAME            = TEME
TIME_SYSTEM          = UTC
START_TIME           = 2019-07-21T00:00:00.000000
STOP_TIME            = 2019-07-22T00:00:00.000000
INTERPOLATION        = LAGRANGE
INTERPOLATION_DEGREE = 7
META_STOP

2019-07-21T00:00:00.000000 -4875.590974 -3634.626046  3023.580912   5.153972  -2.780719   4.941938
2019-07-21T02:00:00.000000  5699.191993 -1430.367113  3390.330521   3.936478   4.677821  -4.632831
2019-07-21T04:00:00.000000  1841.570824  4367.844267 -4869.836690  -7.247029   0.345635  -2.439117
2019-07-21T06:00:00.000000 -6702.230934 -815.971640 -792.346816  -0.107302  -4.830923   5.940230
2019-07-21T08:00:00.000000  1680.296984 -3917.098062  5276.568272   7.324701   2.141783  -0.746824
2019-07-21T10:00:00.000000  5804.888514  2850.542792 -2073.094357  -3.787444   3.702763  -5.539485
2019-07-21T12:00:00.000000 -4775.312315  2441.646806 -4180.032353  -5.325998  -4.038731   3.723697
2019-07-21T14:00:00.000000 -3307.821071 -4082.900715  4297.416402   6.605372  -1.608710   3.538657
2019-07-21T16:00:00.000000  6521.974258 -312.607361  1847.672709   1.838475   4.862894  -5.639923
2019-07-21T18:00:00.000000 -164.416166  4239.669699 -5310.711926  -7.581000  -0.909015  -0.497700
2019-07-21T20:00:00.000000 -6461.450141 -1859.259067  986.720983   2.169861  -4.373022   5.902908
2019-07-21T22:00:00.000000  3566.153656 -3256.158597  4763.011449   6.456894   3.159068  -2.673499
2019-07-22T00:00:00.000000  4558.774191  3548.133531 -3574.431589  -5.603176   2.722130  -4.457432

META_START
OBJECT_NAME          = ISS (ZARYA)
OBJECT_ID            = 1998-067A
CENTER_NAME          = EARTH
REF_FRAME            = TEME
TIME_SYSTEM          = UTC
START_TIME           = 2019-07-19T00:00:00.000000
STOP_TIME            = 2019-07-20T00:00:00.000000
INTERPOLATION        = LAGRANGE
INTERPOLATION_DEGREE = 7
META_STOP

2019-07-19T00:00:00.000000 -5277.564610 -3867.226652  1829.038578   4.198623  -3.041824   5.641019
2019-07-19T02:00:00.000000  4991.230571 -1587.024500  4309.640613   4.634132   4.995956  -3.521679
2019-07-19T04:00:00.000000  2626.870601  4674.829056 -4173.543939  -6.669929   0.422433  -3.736285
2019-07-19T06:00:00.000000 -6417.088455 -833.533894 -2087.243417  -1.120062  -5.177436   5.526344
2019-07-19T08:00:00.000000  734.631058 -4203.713568  5273.129212   7.287480   2.254143   0.773542
2019-07-19T10:00:00.000000  6030.748709  3020.974680 -776.913862  -2.749036   3.977229  -5.950206
2019-07-19T12:00:00.000000 -3950.047806  2621.141859 -4874.886965  -5.847620  -4.294378   2.425832
2019-07-19T14:00:00.000000 -3981.489128 -4344.975078  3372.903458   5.844775  -1.731774   4.644455
2019-07-19T16:00:00.000000  6054.717093 -345.293803  3040.852794   2.780118   5.174557  -4.933402
2019-07-19T18:00:00.000000  761.677399  4505.822052 -5031.306243  -7.329232  -0.963374  -1.980331
2019-07-19T20:00:00.000000 -6494.420028 -1974.687665 -357.930008   1.089140  -4.640865   5.993711
2019-07-19T22:00:00.000000  2650.327499 -3449.024539  5204.019797   6.784764   3.354157  -1.234971
2019-07-20T00:00:00.000000  5087.211254  3762.134249 -2469.553745  -4.699560   2.871919  -5.327809

"""

def test_parse_request(space_tmpdir):

    request = Request.from_text("ISS (ZARYA)")

    assert request.selector == "name"
    assert request.value == "ISS (ZARYA)"
    assert request.offset == 0
    assert request.src == "tle"
    # assert request.limit == ""

    request = Request.from_text("norad=25544~3@oem")

    assert request.selector == "norad_id"
    assert request.value == "25544"
    assert request.offset == 3
    assert request.src == "oem"

    # Selection by alias
    request = Request.from_text("ISS")

    assert request.selector == "norad_id"
    assert request.value == "25544"
    assert request.offset == 0
    assert request.src == "tle"

    request = Request.from_text("norad=25544?2019-02-27")

    assert request.selector == "norad_id"
    assert request.value == "25544"
    assert request.limit == "before"
    assert request.date == Date(2019, 2, 27)

    request = Request.from_text("norad=25544^2019-02-27T12:00:00")

    assert request.selector == "norad_id"
    assert request.value == "25544"
    assert request.limit == "after"
    assert request.date == Date(2019, 2, 27, 12)

    with raises(ValueError):
        request = Request.from_text("norod=25544")


def test_get_sat(space_tmpdir):

    sat = Sat.from_selector("ISS", orb=False)

    assert sat.name == "ISS (ZARYA)"
    assert sat.cospar_id == "1998-067A"
    assert sat.norad_id == 25544
    assert sat.orb == None

    with raises(ValueError):
        sat = Sat.from_selector("XMM", orb=False)


def test_get_tle(space_tmpdir, run):

    r = run("space tle insert - ", stdin=tle2)
    assert r.success

    sat = Sat.from_selector("ISS")

    assert sat.name == "ISS (ZARYA)"
    assert sat.cospar_id == "1998-067A"
    assert sat.norad_id == 25544
    assert sat.orb.date == Date(2019, 6, 10, 5, 43, 40, 581696)

    sat = Sat.from_selector("ISS~")

    assert sat.name == "ISS (ZARYA)"
    assert sat.cospar_id == "1998-067A"
    assert sat.norad_id == 25544
    assert sat.orb.date == Date(2018, 10, 24, 13, 14, 20, 814720)

    with raises(ValueError):
        sat = Sat.from_selector("ISS~3")

    # After the date
    sat = Sat.from_selector("ISS^2018-01-01")
    assert sat.orb.date == Date(2018, 10, 24, 13, 14, 20, 814720)

    # Before the date
    sat = Sat.from_selector("ISS?2018-01-01")
    assert sat.orb.date == Date(2017, 12, 9, 6, 33, 16, 76736)


def test_get_ephem(space_tmpdir, run):

    r = run("space oem insert -", stdin=ephem)
    assert r.success

    sat = Sat.from_selector('ISS@oem')

    assert sat.name == "ISS (ZARYA)"
    assert sat.cospar_id == "1998-067A"
    assert sat.norad_id == 25544
    assert sat.orb.start == Date(2019, 7, 21)
    assert sat.orb.stop == Date(2019, 7, 22)

    sat = Sat.from_selector('ISS@oem~')

    assert sat.orb.start == Date(2019, 7, 19)
    assert sat.orb.stop == Date(2019, 7, 20)  

    with raises(ValueError):
        sat = Sat.from_selector("ISS@oem~3")

    sat = Sat.from_selector('ISS@oem^2019-07-20')
    assert sat.orb.start == Date(2019, 7, 21)
    assert sat.orb.stop == Date(2019, 7, 22)

    sat = Sat.from_selector('ISS@oem?2019-07-20')
    assert sat.orb.start == Date(2019, 7, 19)
    assert sat.orb.stop == Date(2019, 7, 20)

    with raises(ValueError):
        sat = Sat.from_selector('ISS@oem?2019-07-19')