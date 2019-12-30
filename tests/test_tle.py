from pytest import mark
from pathlib import Path


tle1 = """ISS (ZARYA)
1 25544U 98067A   18297.55162980  .00001655  00000-0  32532-4 0  9999
2 25544  51.6407  94.0557 0003791 332.0725 138.3982 15.53858634138630"""

tle2 = """ISS (ZARYA)
1 25544U 98067A   17343.27310274  .00004170  00000-0  70208-4 0  9997
2 25544  51.6420 245.4915 0003135 211.8338 242.8677 15.54121086 88980"""


def test_get(run):

    r = run(("space", "tle", "get", "ISS (ZARYA)"))
    assert not r.stderr
    assert r.stdout.strip() == tle1
    assert r.success


    r = run("space tle get cospar=1998-067A")
    assert not r.stderr
    assert r.stdout.strip() == tle1
    assert r.success


    r = run("space tle get norad=25544")
    assert not r.stderr
    assert r.stdout.strip() == tle1
    assert r.success


    r = run("space tle get UNKNOWN")
    assert not r.success
    assert r.stderr == "No satellite corresponding to name=UNKNOWN\n"
    assert not r.stdout


def test_insert(run):

    filepath = Path(__file__).parent / "data" / "visual.txt"

    r = run("space tle insert {}".format(filepath.absolute()))
    assert r.stderr.startswith("visual.txt")
    assert not r.stdout
    assert r.success

    # globbing
    filepath = Path(__file__).parent / "data" / "*.txt"

    r = run("space tle insert {}".format(filepath.absolute()))
    assert not r.stdout
    assert r.stderr.startswith("visual.txt")
    assert r.success

    # from STDIN
    new_tle = tle2

    r = run("space tle insert -", stdin=new_tle)
    assert r.success
    assert not r.stdout
    assert r.stderr.startswith("stdin")


def test_find(run):

    r = run("space tle find zarya")
    assert r.stderr == "==> 1 entries found for 'zarya'\n"
    assert r.stdout.strip() == tle1
    assert r.success

    r = run("space tle find unknown")
    assert r.stderr == "No TLE containing 'unknown'\n"
    assert not r.stdout
    assert not r.success


def test_stats(run):

    r = run("space tle stats")
    assert not r.stderr

    data = {}
    for line in r.stdout.splitlines():
        k, _, v = line.partition(":")
        data[k.strip().lower()] = v.strip()

    assert int(data["objects"]) >= 1
    assert int(data["tle"]) >= 1
    assert data['first fetch']
    assert data['last fetch']

    assert r.success


def test_dump(run):

    r = run("space tle dump")

    assert not r.stderr
    assert len(r.stdout.splitlines()) == 4  # Exactly one TLE
    assert r.stdout.strip() == tle1
    assert r.success


def test_history(run):

    r = run("space tle insert - ", stdin=tle2)
    assert r.success

    r = run("space tle history norad=25544")
    assert not r.stderr
    assert len(r.stdout.splitlines()) == 8
    assert r.success

    r = run("space tle history UNKNOWN")
    assert r.stderr == "No satellite corresponding to name=UNKNOWN\n"
    assert not r.stdout
    assert not r.success


@mark.skip
def test_celestrak_fetch(run):
    pass


@mark.skip
def test_celestrak_fetch_list(run):
    pass


@mark.skip
def test_spacetrack_fetch(run):
    pass
