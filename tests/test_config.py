
import sys
import pytest

@pytest.mark.skipif(sys.version_info < (3,6), reason="before 3.6 dict where unordered")
def test_get(run):

    # Get full config dict
    r = run("space config")
    out = r.stdout.splitlines()
    assert out[0].startswith("config :")
    assert "\n".join(out[1:]) == """beyond:
    eop:
        missing_policy: pass
stations:
    TLS:
        latlonalt:
            43.604482
            1.443962
            172.0
        name: Toulouse
        parent_frame: WGS84"""
    assert r.stderr == ""
    assert r.success
    
    r = run("space config get beyond.eop.missing_policy")
    assert r.stdout == "pass\n"
    assert not r.stderr
    assert r.success

    # without the 'get' parameter
    r = run("space config stations.TLS.name")
    assert r.success
    assert r.stdout == "Toulouse\n"
    assert not r.stderr

    r = run("space config stations.TEST.name")
    assert not r.success
    assert r.stdout == ""
    assert r.stderr == "Unknown field 'TEST'\n"


def test_reinit(run):
    pass
    # # Try to init a second time
    # r = run("space config init")
    # out = r.stdout
    # err = r.stderr
    # assert not out
    # assert err.startswith("config file already exists at ")
    # assert r.success


def test_unlock(run):
    # Unlocking the config file
    r = run("space config unlock --yes")
    out = r.stdout.splitlines()
    err = r.stderr
    assert err.startswith("Unlocking")
    assert r.success

    # Try to unlock the config file, then cancel
    r = run("space config unlock", stdin="no")
    out = r.stdout.splitlines()
    err = r.stderr
    assert out[0] == "Are you sure you want to unlock the config file ?"
    assert out[1] == " yes/[no] "
    assert not err
    assert r.success

    # Try to unlock the config file, but hit wrong keys
    r = run("space config unlock", stdin="dummy")
    out = r.stdout.splitlines()
    err = r.stderr
    assert out[0] == "Are you sure you want to unlock the config file ?"
    assert out[1] == " yes/[no] "
    assert err == "unknown answer 'dummy'\n"
    assert not r.success

    # Lock file
    r = run("space config lock")
    out = r.stdout
    err = r.stderr
    assert not out
    assert err == "Locking the config file\n"
    assert r.success

    r = run("space config lock")
    out = r.stdout
    err = r.stderr
    assert not out
    assert err == "The config file is already locked\n"
    assert r.success


def test_set(run):

    # Modifying the value in the config file without unlocking
    r = run("space config set stations.TLS.name Anywhere")
    assert not r.stdout
    assert r.stderr == "Config file locked. Please use 'space config unlock' first\n"
    assert not r.success
    
    # Unlocking the config file
    r = run("space config unlock", stdin="yes")
    out = r.stdout.splitlines()
    err = r.stderr.splitlines()
    assert out[0] == "Are you sure you want to unlock the config file ?"
    assert out[1] == " yes/[no] "
    assert err[0].startswith("Unlocking")
    assert r.success

    # Modifying the value in the config file
    r = run("space config set stations.TLS.name Anywhere")
    assert not r.stdout
    assert not r.stderr
    assert r.success

    # Verifying
    r = run("space config stations.TLS.name")
    assert r.stdout == "Anywhere\n"
    assert not r.stderr
    assert r.success

    # Locking
    r = run("space config lock")
    assert not r.stdout
    assert r.stderr == "Locking the config file\n"
    assert r.success

    # Testing that the lock is well in place
    r = run("space config set stations.TLS.name Nowhere")
    assert not r.stdout
    assert r.stderr == "Config file locked. Please use 'space config unlock' first\n"
    assert not r.success