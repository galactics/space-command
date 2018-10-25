from pytest import fixture


@fixture
def run_date(run):
    run("space clock set-date 2018-11-01T09:00:00")
    return run


def test_simple(run_date):

    r = run_date("space passes TLS ISS")
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 27
    assert lines[2].startswith("AOS 0 TLS")
    assert lines[14].startswith("MAX TLS")
    assert lines[-1].startswith("LOS 0 TLS")
    assert not r.stderr
    assert r.success

    # Call containing two satellites (here it is the same one)
    r = run_date("space passes TLS ISS ISS")
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 55
    assert lines[2].startswith("AOS 0 TLS")
    assert lines[14].startswith("MAX TLS")
    assert lines[-1].startswith("LOS 0 TLS")
    assert not r.stderr
    assert r.success

    r = run_date("space passes UNKNOWN ISS")
    lines = r.stdout.strip().splitlines()
    assert r.stderr == "Unknwon station 'UNKNOWN'\n"
    assert not r.stdout
    assert not r.success

    r = run_date("space passes TLS UNKNOWN")
    lines = r.stdout.strip().splitlines()
    assert r.stderr == "Unknwon satellite 'UNKNOWN'\n"
    assert not r.stdout
    assert not r.success


def test_date(run_date):
    
    r = run_date("space passes TLS ISS --date 2018-11-01T11:00:00")

    lines = r.stdout.strip().splitlines()

    assert len(lines) == 23
    assert lines[2].startswith("AOS 0 TLS")
    assert lines[12].startswith("MAX TLS")
    assert lines[-1].startswith("LOS 0 TLS")
    assert not r.stderr
    assert r.success

    r = run_date("space passes TLS ISS --date 2018-11-01 11:00:00")
    assert not r.success
    assert r.stderr == "time data '2018-11-01' does not match format '%Y-%m-%dT%H:%M:%S'\n"
    assert not r.stdout


def test_step(run_date):
    
    r = run_date("space passes TLS ISS --step 10")

    lines = r.stdout.strip().splitlines()

    assert len(lines) == 69
    assert lines[2].startswith("AOS 0 TLS")
    assert lines[35].startswith("MAX TLS")
    assert lines[-1].startswith("LOS 0 TLS")
    assert not r.stderr
    assert r.success
    
    r = run_date("space passes TLS ISS -s hello")
    assert not r.success
    assert r.stderr == "could not convert string to float: 'hello'\n"
    assert not r.stdout


def test_events_only(run_date):

    r = run_date("space passes TLS ISS --events-only")

    lines = r.stdout.strip().splitlines()

    assert len(lines) == 5
    assert lines[2].startswith("AOS 0 TLS")
    assert lines[3].startswith("MAX TLS")
    assert lines[4].startswith("LOS 0 TLS")
    assert not r.stderr
    assert r.success


def test_no_events(run_date):

    r = run_date("space passes TLS ISS --no-events")
    lines = r.stdout.strip().splitlines()
    assert not lines[2].startswith("AOS 0 TLS")
    assert not lines[-1].startswith("LOS 0 TLS")
    assert not r.stderr
    assert r.success


def test_light(run_date):

    # This test is computed for an other pass, in order to actually compute
    # the 'light' events
    r = run_date("space passes TLS ISS --events-only --light --date 2018-11-01T03:00:00")

    lines = r.stdout.strip().splitlines()

    assert len(lines) == 7
    assert lines[2].startswith("AOS 0 TLS")
    assert lines[3].startswith("MAX TLS")
    assert lines[4].startswith("Umbra exit")  # The ISS goes out of the shadow of the earth
    assert lines[5].startswith("Penumbra exit")
    assert lines[6].startswith("LOS 0 TLS")
    assert not r.stderr
    assert r.success