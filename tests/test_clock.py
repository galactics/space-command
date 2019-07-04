

def test_display(run):

    r = run("space clock")

    lines = r.stdout.splitlines()

    assert len(lines) == 3
    assert lines[0].startswith("System Date")
    assert lines[1].startswith("Clock Date")
    # System date and clock date are identical
    assert lines[0].split(":")[-1].strip() == lines[1].split(":")[-1].strip()
    assert lines[2] == "Offset      : 0:00:00"

    assert not r.stderr
    assert r.success


def test_set_date(run):

    # Set the clock to a future, happy date
    r = run("space clock set-date 2018-12-25T00:00:00.000000 2018-11-01T00:00:00.000000")

    assert r.stderr == "Clock date set to 2018-12-25T00:00:00 UTC\n\n"

    lines = r.stdout.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("System Date")
    assert lines[1].startswith("Clock Date")
    assert lines[2] == "Offset      : 54 days, 0:00:00"
    assert r.success

    # For this test case, as it is dependant of the system time,
    # it is very hard to test
    r = run("space clock set-date 2018-12-25T00:00:00.000000")

    assert r.stderr.startswith("Clock date set to 2018-12-25T00:00:00 UTC")

    lines = r.stdout.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("System Date")
    assert lines[1].startswith("Clock Date")
    assert lines[2].startswith("Offset")
    assert r.success


def test_set_offset(run):

    r = run("space clock set-offset 500s")

    assert r.stderr == "Clock offset set to 0:08:20\n\n"

    lines = r.stdout.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("System Date")
    assert lines[1].startswith("Clock Date")
    assert lines[2] == "Offset      : 0:08:20"
    assert r.success

    # Negative offset
    r = run("space clock set-offset -500s")

    assert r.stderr.startswith("Clock offset set to -1 day, 23:51:40\n\n")

    lines = r.stdout.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("System Date")
    assert lines[1].startswith("Clock Date")
    assert lines[2] == "Offset      : -1 day, 23:51:40"
    assert r.success


def test_set_then_sync(run):

    # Set the clock to a future, happy date
    r = run("space clock set-date 2018-12-25T00:00:00.000000 2018-11-01T00:00:00.000000")

    assert r.stderr == "Clock date set to 2018-12-25T00:00:00 UTC\n\n"

    lines = r.stdout.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("System Date")
    assert lines[1].startswith("Clock Date")
    assert lines[2] == "Offset      : 54 days, 0:00:00"
    assert r.success

    r = run("space clock sync")
    lines = r.stdout.splitlines()

    assert len(lines) == 3
    assert lines[0].startswith("System Date")
    assert lines[1].startswith("Clock Date")
    # System date and clock date are identical
    assert lines[0].split(":")[-1].strip() == lines[1].split(":")[-1].strip()
    assert lines[2] == "Offset      : 0:00:00"

    assert r.stderr == "Clock set to system time\n\n"
    assert r.success
