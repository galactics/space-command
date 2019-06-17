import os
import random
from io import StringIO
from pytest import yield_fixture, fixture

from space.wspace import switch_workspace
from space.tle import TleDb
from space.sat import sync_tle


@fixture
def space_tmpdir():

    name = 'tmp-pytest'

    with switch_workspace(name, init=True, delete=True) as ws:

        TleDb().insert("""ISS (ZARYA)
1 25544U 98067A   18297.55162980  .00001655  00000-0  32532-4 0  9999
2 25544  51.6407  94.0557 0003791 332.0725 138.3982 15.53858634138630""", src='stdin')

        # Synchronize the Satellite database with the TleDatabase
        sync_tle()
        yield ws


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
