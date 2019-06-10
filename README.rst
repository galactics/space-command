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

* Retrieve orbits as TLE from celestrak or space-track
* Compute visibility from a given point of observation
* Compute phases of the Moon and other solar system bodies
* Animated map of satellites' orbit
* Compute events for a given satellite (day/night, node, AOS/LOS, etc.)
* Retrieve Solar System bodies ephemeris

See `documentation <https://space-command.readthedocs.io/en/latest/>`__ for a
list of all the features.

Changelog
---------

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