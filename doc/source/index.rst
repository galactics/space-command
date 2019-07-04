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

    wspace init        # Create the empty workspace structure
    space tle fetch    # Retrieve orbital data for major satellites

Stations are accessed by their abbreviation, and by default there is only
one declared: TLS. As it is not likely you live in this area, you need to
declare a new station of observation.

.. code-block:: shell

    space station create                # Interactively create a station
    space station --map                 # Check if your station is well where you want it to be
    space passes <abbrev> "ISS (ZARYA)"  # Compute the next pass of the ISS from your location

When a satellite name is needed in a command, it's the full name of the satellite is expected,
as defined on the TLE. Alternatively you can access satellites by their identifiers
(NORAD ID or COSPAR ID). All following commands are equivalent

.. code-block :: shell

    space passes <station> norad=25544
    space passes <station> cospar=1998-067A
    space passes <station> "name=ISS (ZARYA)"
    space passes <station> "ISS (ZARYA)"

Sometimes the full name is rather complex (e.g. "ISS (ZARYA)"), so you can define
aliases as follow

.. code-block:: shell

    space sat alias ISS norad=25544

The alias 'ISS' is already defined.

To avoid creating thousand of abbreviations, you can just chain commands as
demonstrated in :ref:`pipping`.

Available commands
------------------

For full details on a command, use ``-h`` or ``--help`` arguments

``space events`` : Compute events encountered by the satellite : day/night transitions, AOS/LOS from stations, Node crossing, Apoapsis and Periapsis, etc.

``space map`` : Display an animated map of Earth with the satellites

``space passes`` : Compute visibility geometry (azimuth/elevation) from a given ground station

``space phase`` : Compute and display the phase of the Moon and other solar system bodies

``space planet`` : Compute the position of planets

``space station`` : Create and display ground stations

``space tle`` : Retrieve TLEs from Celestrak or Space-Track, store them and consult them

Command Argmuents
^^^^^^^^^^^^^^^^^

**Dates**

If not specified otherwise, dates should be given following the ISO 8601
format %Y-%m-%dT%H:%M:%S. You can also use the keywords 'now', 'midnight' and 'tomorrow'.

**Time range**

Time ranges may be expressed in weeks (*w*), days (*d*), hours (*h*), minutes (*m*) or seconds (*s*):

    - `600s` is 600 seconds (10 minutes)
    - `2w7h` is 2 weeks and 7 hours
    - `3h20.5m` is 3 hours 20 minutes and 30 seconds

All descriptors except weeks accept decimals.

**Satellite Name**

Workspaces
^^^^^^^^^^

Workspaces allow the user to work on non-colluding databases. They 

.. _pipping:

Pipping commands
^^^^^^^^^^^^^^^^

It is possible to chain commands in order to feed a result from one to another.
In this case, the name of the satellite should be replaced by ``-`` in the second
command.

.. code-block:: shell

    # Compute the pass of Mars above a station
    space planet Mars | space passes TLS - -s 600 -g

    # Search for TLEs and display them on a map
    space tle find tintin | space map -

Extension
---------

It is possible to create your own scripts and extensions to this framework.

To do that you have to create a ``space.commands`` `entry point <https://amir.rachum.com/blog/2017/07/28/python-entry-points/>`__.
This will declare the extension to space-command, and make it available as an
additional subcommand.

If you need to extend the initialisation process (``wspace init``), the entry point
is ``space.wshook``.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
