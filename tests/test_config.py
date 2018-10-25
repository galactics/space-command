

def test_get(run):
    
    r = run("space config get aliases.ISS")
    assert r.stdout == "25544\n"
    assert not r.stderr
    assert r.success

    # without the 'get' parameter
    r = run("space config stations.TLS.name")
    assert r.success
    assert r.stdout == "Toulouse\n"
    assert not r.stderr


def test_set(run):

    # Modifying the value in the config file without unlocking
    r = run("space config set stations.TLS.name Anywhere")
    assert not r.stdout
    assert r.stderr == "Config file locked. Please use 'space config unlock' first\n"
    assert not r.success
    
    # Unlocking the config file
    r = run("space config unlock", stdin="yes")
    assert not r.stderr
    out = r.stdout.splitlines()
    assert out[0] == "Are you sure you want to unlock the config file ?"
    assert out[1] == " yes/[no] "
    assert out[2] == "A backup of the current config file has been created at"
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
    assert not r.stderr
    assert r.success

    # Testing that the lock is well in place
    r = run("space config set stations.TLS.name Nowhere")
    assert not r.stdout
    assert r.stderr == "Config file locked. Please use 'space config unlock' first\n"
    assert not r.success