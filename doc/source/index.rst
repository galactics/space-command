.. space-command documentation master file, created by
   sphinx-quickstart on Sun Feb 24 21:11:04 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

space-command
=============

Features
--------

 * Retrieve orbits as TLE from celestrak or space-track
 * Compute visibility from a given point of observation
 * Compute phases of the Moon and other solar system bodies
 * Animated map of the orbit of satellites
 * Compute events for a given satellite (day/night, node, AOS/LOS, etc.)
 * Retrieve Solar System bodies ephemeris

Installation
------------

.. code-block:: shell

    pip install space

If you need the last development version, make sure to also install
the last version of `beyond <https://github.com/galactics/beyond>`__, which space
relies heavily upon.

.. code-block:: shell

    pip install git+https://github.com/galactics/beyond
    pip install git+https://github.com/galactics/space-command

Quick start
-----------

.. code-block:: shell

    space config init  # Create the basic environment to work
    space tle fetch  # Retrieve orbital data for major satellites
    space planets fetch  # Retrieve planets ephemeris

Stations are accessed by their abbreviation, and by default there is only
one declared: TLS. As it is not likely you live in this area, you need to
declare a new station of observation.

.. code-block:: shell

    space stations create  # Interactively create a station
    space stations --map  # Check if your station is well where you want it to be

    space passes <abbrev> ISS  # Compute the next pass of the ISS from your location

When a satellite name is needed in a command, it's the full name of the satellite,
as defined on the TLE, which is expected. Sometimes the full name is rather
complex (e.g. "ISS (ZARYA)"), so you can define aliases in the config file.
The alias 'ISS' is already defined.

To avoid creating thousand of abbreviations, you can just chain commands as
demonstrated below.

Available commands
------------------

def space_stations(*argv):
For full details on a command, use ``-h`` or ``--help`` arguments

``space events`` : Compute events encountered by the satellite : day/night transitions, AOS/LOS from stations, Node crossing, Apoapsis and Periapsis, etc.

``space map`` : Display an animated map of Earth with the satellites

``space passes`` : Compute visibility geometry (azimuth/elevation) from a given ground station

``space phase`` : Compute and display the phase of the Moon and other solar system bodies

``space planets`` : Compute the position of planets

``space stations`` : Create and display ground stations

``space tle`` : Retrieve TLEs from Celestrak or Space-Track, store them and consult them

It is possible to chain commands in order to feed a result from one to another.
In this case, the name of the satellite should be replaced by ``-`` in the second
command.

.. code-block:: shell

    # Compute the pass of Mars above a station
    space planets Mars | space passes TLS - -s 600 -g

    # Search for TLEs and display them on a map
    space tle find tintin | space map -

Extension
---------

It is possible to create your own scripts and extensions to this framework.

To do that you have to create a ``space.commands`` `entry point <https://amir.rachum.com/blog/2017/07/28/python-entry-points/>`__.
This will declare the extension to space-command, and make it available as an
additional subcommand.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
