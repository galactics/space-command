from pytest import fixture


@fixture
def run_date(run):
    run("space clock set-date 2018-11-01T09:00:00.000000")
    return run


def test_simple(run_date):

    r = run_date("space passes TLS ISS --csv")
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 26
    assert lines[1].split(',')[1] == "AOS 0 TLS"
    assert lines[13].split(',')[1] == "MAX TLS"
    assert lines[-1].split(',')[1] == "LOS 0 TLS"
    assert not r.stderr
    assert r.success

    # Call containing two satellites (here it is the same one)
    r = run_date("space passes TLS ISS ISS --csv")
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 53
    assert lines[1].split(',')[1] == "AOS 0 TLS"
    assert lines[13].split(',')[1] == "MAX TLS"
    assert lines[-1].split(',')[1] == "LOS 0 TLS"
    assert not r.stderr
    assert r.success

    r = run_date("space passes UNKNOWN ISS --csv")
    lines = r.stdout.strip().splitlines()
    assert r.stderr == "Unknwon station 'UNKNOWN'\n"
    assert not r.stdout
    assert not r.success

    r = run_date("space passes TLS UNKNOWN --csv")
    lines = r.stdout.strip().splitlines()
    assert r.stderr == "No satellite corresponding to name=UNKNOWN\n"
    assert not r.stdout
    assert not r.success


def test_date(run_date):
    
    r = run_date("space passes TLS ISS --date 2018-11-01T11:00:00 --csv")

    lines = r.stdout.strip().splitlines()

    assert len(lines) == 22
    assert lines[1].split(',')[1] == "AOS 0 TLS"
    assert lines[11].split(',')[1] == "MAX TLS"
    assert lines[-1].split(',')[1] == "LOS 0 TLS"
    assert not r.stderr
    assert r.success

    r = run_date("space passes TLS ISS --date 2018-11-01 11:00:00 --csv")
    assert not r.success
    assert r.stderr == "No satellite corresponding to name=11:00:00\n"
    assert not r.stdout


def test_step(run_date):
    
    r = run_date("space passes TLS ISS --step 10s --csv")

    lines = r.stdout.strip().splitlines()

    assert len(lines) == 68
    assert lines[1].split(',')[1] == "AOS 0 TLS"
    assert lines[34].split(',')[1] == "MAX TLS"
    assert lines[-1].split(',')[1] == "LOS 0 TLS"
    assert not r.stderr
    assert r.success
    
    r = run_date("space passes TLS ISS -s hello --csv")
    assert not r.success
    assert r.stderr == "No timedelta found in 'hello'\n"
    assert not r.stdout


def test_events_only(run_date):

    r = run_date("space passes TLS ISS --events-only --csv")

    lines = r.stdout.strip().splitlines()

    assert len(lines) == 4
    assert lines[1].split(',')[1] == "AOS 0 TLS"
    assert lines[2].split(',')[1] == "MAX TLS"
    assert lines[3].split(',')[1] == "LOS 0 TLS"
    assert not r.stderr
    assert r.success


def test_no_events(run_date):

    r = run_date("space passes TLS ISS --no-events --csv")
    lines = r.stdout.strip().splitlines()
    assert not lines[2].startswith("AOS 0 TLS")
    assert not lines[-1].startswith("LOS 0 TLS")
    assert not r.stderr
    assert r.success


def test_light(run_date):

    # This test is computed for an other pass, in order to actually compute
    # the 'light' events
    r = run_date("space passes TLS ISS --events-only --light --date 2018-11-01T03:00:00 --csv")

    lines = r.stdout.strip().splitlines()

    assert len(lines) == 6
    assert lines[1].split(',')[1] == "AOS 0 TLS"
    assert lines[2].split(',')[1] == "MAX TLS"
    assert lines[3].split(',')[1] == "Umbra exit"
    assert lines[4].split(',')[1] == "Penumbra exit"
    assert lines[5].split(',')[1] == "LOS 0 TLS"

    assert not r.stderr
    assert r.success