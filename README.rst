Space Command
=============

The space command allows to compute the position of satellites and their passes above our head.

In order to do this, it uses the `beyond <https://github.com/galactics/beyond>`__ library.

Installation
------------

.. code-block:: shell

    $ pip install space-command

Features
--------

**Retrieve orbits as TLE from celestrak**

.. code-block:: shell

    $ space tle get
    $ space tle name ISS
    ISS (ZARYA)
    1 25544U 98067A   18217.29289738  .00001607  00000-0  31893-4 0  9999
    2 25544  51.6423 133.9734 0005443  28.3880 115.1824 15.53801660126150

**Animated map showing position of a satellite (e.g. the ISS)**

.. code-block:: shell

    $ space map ISS

**Compute and display moon phase**

.. code-block:: shell

    $ space moon <station> --graph

**Retrieve Solar System bodies ephemeris**

.. code-block:: shell

    $ space planets Moon
    $ space planets Mars Jupiter Saturn

**Predict passes of planets or satellites**

.. code-block:: shell

    $ space planets Mars | space passes <station> -
    $ space tle find OSCAR 7 | space passes <station> -

Changelog
---------

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
- Centralised date handling, via command ``space clock``
- Allow TLE retrieval from Space-Track

**Chaged**

- Database classes are now suffixed with *Db*
- Subcommand retriving data from the web now use the argument **fetch** instead of get.

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
- Every command taking object names can also take TLE or CCSDS ephemerides via stdin
- add mask handling for stations
- Passes zenital display optional

**Changed**

- MIT licence replace GPLv3

**Removed**

- EOP database disabled by default.