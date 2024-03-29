from pytest import fixture, mark


opm = """CCSDS_OPM_VERS = 2.0
CREATION_DATE = 2020-09-21T21:08:52.972990
ORIGINATOR = N/A

META_START
OBJECT_NAME          = ISS (ZARYA)
OBJECT_ID            = 1998-067A
CENTER_NAME          = EARTH
REF_FRAME            = TEME
TIME_SYSTEM          = UTC
META_STOP

COMMENT  State Vector
EPOCH                = 2020-09-21T21:08:52.000000
X                    =  5689.991323 [km]
Y                    =  -517.601324 [km]
Z                    =  3632.861669 [km]
X_DOT                =     3.298781 [km/s]
Y_DOT                =     5.367726 [km/s]
Z_DOT                =    -4.383843 [km/s]

COMMENT  Keplerian elements
SEMI_MAJOR_AXIS      =  6775.311044 [km]
ECCENTRICITY         =     0.001442
INCLINATION          =    51.641968 [deg]
RA_OF_ASC_NODE       =   205.014391 [deg]
ARG_OF_PERICENTER    =    75.306756 [deg]
TRUE_ANOMALY         =    61.515845 [deg]
GM                   = 398600.9368 [km**3/s**2]

USER_DEFINED_PROPAGATOR = KeplerNum
USER_DEFINED_PROPAGATOR_STEP_SECONDS = 60.000
USER_DEFINED_PROPAGATOR_METHOD = rk4

"""

oem = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2020-09-21T21:17:49.633392
ORIGINATOR = N/A

META_START
OBJECT_NAME          = ISS (ZARYA)
OBJECT_ID            = 1998-067A
CENTER_NAME          = EARTH
REF_FRAME            = TEME
TIME_SYSTEM          = UTC
START_TIME           = 2020-09-21T21:08:52.000000
STOP_TIME            = 2020-09-21T22:08:52.000000
INTERPOLATION        = LAGRANGE
INTERPOLATION_DEGREE = 8
META_STOP

2020-09-21T21:08:52.000000  5689.991323 -517.601324  3632.861669   3.298781   5.367726  -4.383843
2020-09-21T21:11:52.000000  6161.765801  452.628043  2773.758009   1.924976   5.375256  -5.128616
2020-09-21T21:14:52.000000  6378.189208  1404.099824  1799.376321   0.471416   5.160035  -5.660241
2020-09-21T21:17:52.000000  6330.321701  2297.391535  750.218778  -1.001360   4.731078  -5.956571
2020-09-21T21:20:52.000000  6020.235937  3095.521594 -330.107056  -2.431979   4.106404  -6.005387
2020-09-21T21:23:52.000000  5460.924688  3765.507642 -1396.733532  -3.760924   3.312256  -5.804946
2020-09-21T21:26:52.000000  4675.729838  4279.745106 -2405.428362  -4.933137   2.381918  -5.364016
2020-09-21T21:29:52.000000  3697.323491  4617.143235 -3314.451298  -5.900366   1.354207  -4.701397
2020-09-21T21:32:52.000000  2566.300291  4763.967959 -4086.281823  -6.623130   0.271751  -3.844994
2020-09-21T21:35:52.000000  1329.454636  4714.363947 -4689.146194  -7.072226  -0.820846  -2.830507
2020-09-21T21:38:52.000000  37.833934  4470.545361 -5098.282524  -7.229733  -1.878825  -1.699870
2020-09-21T21:41:52.000000 -1255.348375  4042.663793 -5296.908407  -7.089554  -2.859031  -0.499511
2020-09-21T21:44:52.000000 -2496.855763  3448.371858 -5276.867037  -6.657525  -3.721537   0.721466
2020-09-21T21:47:52.000000 -3635.558985  2712.105208 -5038.941232  -5.951138  -4.431136   1.913150
2020-09-21T21:50:52.000000 -4624.481460  1864.111713 -4592.829744  -4.998909  -4.958663   3.026699
2020-09-21T21:53:52.000000 -5422.700128  939.255275 -3956.785599  -3.839386  -5.282167   4.016216
2020-09-21T21:56:52.000000 -5997.033426 -24.370498 -3156.920500  -2.519786  -5.387861   4.840584
2020-09-21T21:59:52.000000 -6323.450638 -986.980404 -2226.184403  -1.094239  -5.270818   5.465212
2020-09-21T22:02:52.000000 -6388.129844 -1908.730613 -1203.047199   0.378335  -4.935345   5.863597
2020-09-21T22:05:52.000000 -6188.104114 -2751.382937 -129.923846   1.836671  -4.394945   6.018597
2020-09-21T22:08:52.000000 -5731.446653 -3479.926595  948.597946   3.219819  -3.671853   5.923313
"""


@fixture(params=["opm", "oem"])
def cmd(request, run):
    r = run(("space", request.param, "compute", "ISS@tle", "--insert"))
    assert r.success
    return request.param


def test_compute_opm(run):
    r = run(("space", "opm", "compute", "ISS@tle", "-d", "2020-09-21T21:08:52"))
    assert r.success
    assert r.stdout.splitlines()[2:] == opm.splitlines()[2:]

    r = run(("space", "opm", "compute", "ISS@tle", "--frame", "EME2000"))
    assert r.success


def test_compute_oem(run):
    r = run(("space", "oem", "compute", "ISS@tle", "-d", "2020-09-21T21:08:52", "-r", "1h"))
    assert r.success
    assert r.stdout.splitlines()[2:] == oem.splitlines()[2:]

def test_list(run, cmd):
    r = run(("space", cmd, "list", "ISS"))

    assert r.success


def test_get(run, cmd):
    r = run(("space", cmd, "get", "ISS"))
    assert r.success
