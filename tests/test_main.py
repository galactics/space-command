import space
import beyond


def test_as_package(run):
    """Invocation of the space command via python packages

    use the ```if __name__ == "__main__"``` at the bottom of the 
    __main__.py file
    """

    r = run("python -m space")
    assert r.stdout
    assert not r.stderr
    assert not r.success


def test_list_subcommands(run):
    """The space command without argument display the list of
    available subcommands and options
    """

    r = run("space")

    data = {}
    mode = "subcommands"
    for line in r.stdout.splitlines()[3:]:
        if not line:
            continue
        elif line == "Available addons sub-commands :":
            mode = "addons"
            continue
        elif line == "Options :":
            mode = "options"
            continue
        if line[0] != " ":
            # If the line is not indented, then it's not a valid subcommand
            # or option, but a mere text
            continue

        subdict = data.setdefault(mode, {})

        k, _, v = line.strip().partition(" ")
        subdict[k] = v.strip()

    assert list(sorted(data['subcommands'].keys())) == [
        "clock", "config", "events", "log", "map", "oem", "opm",
        "passes", "phase", "planet", "sat", "station", "tle"
    ]

    assert list(sorted(data['options'].keys())) == [
        "--no-color", "--pdb", "--version", "-v,", "-w,"
    ]

    assert not r.stderr
    assert not r.success


def test_version(run):

    r = run("space --version")

    lines = r.stdout.splitlines()

    assert len(lines) == 2
    assert lines[0].split() == ["space-command" , space.__version__]
    assert lines[1].split() == ["beyond" , beyond.__version__]

    assert not r.stderr
    assert not r.success
