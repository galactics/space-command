import sys
from pytest import mark, fixture
from pathlib import Path


@fixture
def jpl(run):
    r = run("space config unlock", stdin="yes")
    assert r.success
    r = run("space config set beyond.env.jpl.files --append {}".format(Path(__file__).parent / "data" / "de403_2000-2020.bsp"))
    assert r.success

    r = run("space clock set-date 2020-01-01T00:00:00.000")
    assert r.success

    yield run

    r = run("space clock sync")
    assert r.success


def test_list_analytical(run):

    r = run("space planet")
    assert r.stdout == "List of all available bodies\n Sun\n Moon\n"
    assert not r.stderr
    assert r.success


@mark.skipif(sys.version_info < (3,6), reason="Unpredictible order before 3.6")
def test_list_jpl(jpl, run):

    r = run("space planet")
    assert r.stdout == """List of all available bodies
  EarthBarycenter
  ├─ SolarSystemBarycenter
  │  ├─ MercuryBarycenter
  │  │  └─ Mercury
  │  ├─ VenusBarycenter
  │  │  └─ Venus
  │  ├─ MarsBarycenter
  │  │  └─ Mars
  │  ├─ JupiterBarycenter
  │  ├─ SaturnBarycenter
  │  ├─ UranusBarycenter
  │  ├─ NeptuneBarycenter
  │  ├─ PlutoBarycenter
  │  └─ Sun
  ├─ Moon
  Earth

"""

    assert not r.stderr
    assert r.success


def test_ephem_analytical(run):

    r = run("space planet Sun")
    lines = r.stdout.splitlines()
    assert len(lines) == 89
    assert lines[0] == "CCSDS_OEM_VERS = 2.0"
    assert not r.stderr
    assert r.success

    r = run("space planet Mars")
    assert not r.stdout
    assert r.stderr == "Unknown body 'Mars'\n"
    assert not r.success


def test_ephem_jpl(jpl, run):

    r = run("space planet Mars")
    lines = r.stdout.splitlines()
    assert len(lines) == 89
    assert lines[0] == "CCSDS_OEM_VERS = 2.0"
    assert not r.stderr
    assert r.success


@mark.skip
def test_fetch(run):
    pass
