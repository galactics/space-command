
import subprocess
from io import StringIO
from pytest import fixture


@fixture()
def space_tmpdir(tmpdir_factory):
    tmp = tmpdir_factory.mktemp("space")

    # Initialise config
    r = subprocess.run(
        'space config init .'.split(),
        cwd=str(tmp), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    stdout = r.stdout.decode()

    assert r.returncode == 0
    assert stdout.startswith('config creation at')
    assert not r.stderr

    # Insert one TLE in order to have something to work with
    r = subprocess.Popen(
        'space tle insert'.split(),
        cwd=str(tmp), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.PIPE
    )

    stdout, stderr = r.communicate(input=b"""ISS (ZARYA)
1 25544U 98067A   18297.55162980  .00001655  00000-0  32532-4 0  9999
2 25544  51.6407  94.0557 0003791 332.0725 138.3982 15.53858634138630""")

    stderr = stderr.decode()

    assert r.returncode == 0
    assert stderr.startswith('stdin')
    assert not stdout

    return tmp


@fixture
def run(script_runner, space_tmpdir):
    """Launch the space command in the dedicated tmp workdir
    """

    def _run(txt, stdin=None):

        kwargs = {'cwd': str(space_tmpdir)}

        if stdin:
            kwargs['stdin'] = StringIO(stdin)

        return script_runner.run(*txt.split(), **kwargs)

    return _run