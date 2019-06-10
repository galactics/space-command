import os
import subprocess
from io import StringIO
from pytest import yield_fixture, fixture
from unittest.mock import patch


@yield_fixture()
def space_tmpdir(tmpdir_factory):

    tmp_ws = "tmp-pytest"

    r = subprocess.Popen(
        'wspace delete {}'.format(tmp_ws).split(),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    stdout, stderr = r.communicate(input=tmp_ws.encode())

    # Initialise config
    r = subprocess.run(
        'wspace init {}'.format(tmp_ws).split(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    assert r.returncode == 0
    # assert r.stderr
    # assert not r.stdout

    # Insert one TLE in order to have something to work with
    r = subprocess.Popen(
        'space tle insert - -w {}'.format(tmp_ws).split(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.PIPE
    )

    stdout, stderr = r.communicate(input=b"""ISS (ZARYA)
1 25544U 98067A   18297.55162980  .00001655  00000-0  32532-4 0  9999
2 25544  51.6407  94.0557 0003791 332.0725 138.3982 15.53858634138630""")

    stderr = stderr.decode()

    assert r.returncode == 0
    # assert stderr.startswith('stdin')
    # assert not stdout

    # Initialize config to take satellite into account
    r = subprocess.run(
        'wspace init {}'.format(tmp_ws).split(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    try:
        yield
    finally:

        r = subprocess.Popen(
            'wspace delete {}'.format(tmp_ws).split(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout, stderr = r.communicate(input=tmp_ws.encode())

        assert r.returncode == 0
    # assert stdout.decode().strip().endswith("deleted")
    # assert not stderr


@fixture
def run(script_runner, space_tmpdir):
    """Launch the space command in the dedicated tmp workdir
    """

    def _run(txt, stdin=None):

        # kwargs = {'cwd': str(space_tmpdir)}
        kwargs = {}

        if stdin:
            kwargs['stdin'] = StringIO(stdin)

        kwargs['env'] = os.environ.copy()
        kwargs['env']['SPACE_WORKSPACE'] = 'tmp-pytest'

        return script_runner.run(*txt.split(), **kwargs)

    return _run
