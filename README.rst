Space Command
=============

.. image:: http://readthedocs.org/projects/space-command/badge/?version=latest
    :alt: Documentation Status
    :target: https://space-command.readthedocs.io/en/latest/?badge=latest

.. image:: https://img.shields.io/pypi/v/space-command.svg
    :alt: PyPi version
    :target: https://pypi.python.org/pypi/space-command

.. image:: https://img.shields.io/pypi/pyversions/space-command.svg
    :alt: Python versions
    :target: https://pypi.python.org/pypi/space-command

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

The space command allows to compute the position of satellites and their passes above our head.

In order to do this, it uses the `beyond <https://github.com/galactics/beyond>`__ library.

Installation
------------

For the stable release

.. code-block:: shell

    $ pip install space-command

For the latest development version

.. code-block:: shell

    $ pip install git+https://github.com/galactics/beyond
    $ pip install git+https://github.com/galactics/space-command

Features
--------

* Retrieve orbits as TLE from `Celestrak <http://celestrak.com/>`__ or `Space-Track <https://www.space-track.org/>`__
* Compute visibility from a given point of observation
* Compute phases of the Moon and other solar system bodies
* Animated map of the orbit of satellites
* Compute events for a given satellite (day/night, node, AOS/LOS, etc.)
* Retrieve Solar System bodies ephemeris

See `documentation <https://space-command.readthedocs.io/en/latest/>`__ for a
list of all the features.

Changelog
---------

[0.7] - 2020-08-11
^^^^^^^^^^^^^^^^^^

**Added**

- ``space tle`` history range selection
- ``wspace backup`` command to create, list and restore workspaces backups
- ``orb2circle()`` function to quickly compute the circle of visibility of a spacecraft
- ``space opm`` and ``space oem`` commands for OPM and OEM handling.
- ``tox`` passes command-line arguments to ``pytest`` if provided after ``--``

**Modified**

- refactoring of ``space map``, as a subpackage
- ``parse_date()`` tries both default date format ("%Y-%m-%dT%H:%M:%S" and "%Y-%m-%d"),
  allowing for more relaxed dates command arguments
- refactoring ``space sat`` with documentation on each function

**Removed**

- ``space ephem`` is replaced by ``space oem``
- ``space station`` does not allow interactive station creation anymore

[0.6] - 2020-01-01
^^^^^^^^^^^^^^^^^^

**Added**

- `black <https://black.readthedocs.io/en/stable/>`__ code style
- Retrieve available pages from Celestrak
- Parse time scale of a datetime argument (i.e. "2020-01-01T14:36:00 TAI")
- ``wspace`` can list and restore backups
- ``space planet`` display the download progress
- Support of Python 3.8
- ``space events`` can compute Argument Of Latitude, and specific stations events
- ``space map`` command arguments to start at a given date, disable ground track or disable visibility circle

**Modified**

- ``Sat.from_selector`` take a single selector and return a single Sat instance.
  Use ``Sat.from_selectors()`` for a generator.
- Refactoring the *space.tle* module into a subpackage

**Fixed**

- Correction of sorting algorithm for ``space tle``
- ``space passes`` header
- Support of environment variable to set a proxy, even in async code
- ``map`` does not crash when an ephemeris is out of bound

**Removed**

- Support of python 3.5
- Unused imports

[0.5] - 2019-07-30
^^^^^^^^^^^^^^^^^^

**Added**

- ``space map`` shows groundtrack
- ``space events`` can selectively display one type of event
- ``space sat`` subcommand to handle the satellite database
- ``space ephem`` subcommand to handle ephemerides
- ``wspace`` for workspace management
- ``space passes`` now has a csv output format
- ``space planet`` is able to fetch any bsp file defined in the config file

**Modified**

- Time span inputs normalized for all commands (20s, 3d12h5m, etc.)
- Satellites can now be accessed by other identifiers than name (norad=25544 and cospar=1998-067A are equivalent to "ISS (ZARYA)"). See ``space sat``
- Logging is now with a timed rotating file

[0.4.2] - 2019-02-23
^^^^^^^^^^^^^^^^^^^^

**Added**

- Logging
- Tests
- ``space events`` subcommand computes all orbital events of a satellite (AOS/LOS, Apogee/Perigee, etc.)
- ``space phase`` to compute the phase of available planets and moons
- groundtracks optional on map

**Removed**

- ``space moon`` subcommand. This is now handled by the more generic ``space phase``

[0.4.1] - 2018-11-01
^^^^^^^^^^^^^^^^^^^^

**Added**

- TLE database dump and statistics
- Station map
- Stations' characteristics defined in config file are now set as attributes of the
  station object

[0.4] - 2018-10-20
^^^^^^^^^^^^^^^^^^

**Added**

- Compute ephemeris of solar system bodies (Moon, Mars, Jupiter, Titan, etc.)
- Moon phase computation
- Centralized date handling, via command ``space clock``
- Allow TLE retrieval from Space-Track

**Changed**

- Database classes are now suffixed with *Db*
- Subcommand retrieving data from the web now use the argument **fetch** instead of get.

**Removed**

- Light propagation delay no longer taken into account.
  The computation was tedious, and has been removed from the beyond library

[v0.3] - 2018-07-24
^^^^^^^^^^^^^^^^^^^

**Added**

- Possibility to create your own commands with the ``space.command`` `entry point <https://setuptools.readthedocs.io/en/latest/pkg_resources.html#entry-points>`__.
- Search TLE containing a string
- Retrieve all chronological TLE of an object
- ``space map`` displays real-time position of objects
- Compute moon phase
- Every command taking object names can also take TLE or CCSDS ephemeris via stdin
- add mask handling for stations
- Passes zenithal display optional

**Changed**

- MIT license replace GPLv3

**Removed**

- EOP database disabled by default.