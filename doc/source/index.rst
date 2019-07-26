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

``space ephem`` : Compute Ephemeris and manage Ephemeris database

In addition, the following commands allow you to access non orbital informations

``space clock`` : Handle the time

``space config`` : Allow to get and set different values to change the way the space command behaves

``space log`` : Access the log of all space commands

Command Argmuents
^^^^^^^^^^^^^^^^^

Dates
"""""
Unless otherwise specified, dates should be given following the ISO 8601
format ``%Y-%m-%dT%H:%M:%S``. You can also use the keywords 'now', 'midnight' and 'tomorrow'.
All dates are expressed in UTC

Example: It is *2019-07-04T20:11:37*, ``now`` will yield *2019-07-04T20:11:37*, ``midnight`` will yield *2019-07-04T00:00:00*, and ``tomorrow`` will yield *2019-07-05T00:00:00*.

Dates are generally used to give the starting point of a computation.

Time range
""""""""""
Time ranges may be expressed in weeks (*w*), days (*d*), hours (*h*), minutes (*m*) or seconds (*s*).
All descriptors except weeks accept decimals:

    - ``600s`` is 600 seconds (10 minutes)
    - ``2w7h`` is 2 weeks and 7 hours
    - ``3h20.5m`` is 3 hours 20 minutes and 30 seconds

Time ranges are generally used to give the ending point and the step size of a computation.

Station selection
"""""""""""""""""
Station selection is done using the abbreviation of the station. By default, only the station
``TLS`` (located in Toulouse, France) is present.

Satellite selection
"""""""""""""""""""
Satellite selection, or rather *Orbit selection* can be made multiple ways.
First you have to pick the descriptor of the satellite.
For instance, the International Space Station (ISS) can be accessed by its name
(``ISS (ZARYA)``), NORAD ID (``25544``), or COSPAR ID ``1998-067A``. The following
commands are equivalent

.. code-block:: bash

    $ space passes TLS name="ISS (ZARYA)"
    $ space passes TLS "ISS (ZARYA)"   # default to name field
    $ space passes TLS norad=25544
    $ space passes TLS cospar=1998-067A

As this could be a bit tiresome, it is possible to define aliases.

.. code-block:: shell

    space sat alias ISS norad=25544

The ``ISS`` alias is already defined

Then, you have to decide which source you want to compute from.
By default, space-command uses TLE previously fetched, but this behaviour
can be overridden.
In some cases, it is not possible to retrieve TLEs for a given object, particularly
if this object is an interplanetary spacecraft. In this case, we have to rely on
ephemeris files (OEM).

**Examples**

.. code-block:: bash

    $ space passes TLS ISS      # Use the latest TLE
    $ space passes TLS ISS@tle  # Use the latest TLE
    $ space passes TLS ISS@oem  # Use the latest OEM

.. code-block:: text

    ISS                : latest TLE of ISS
    norad=25544        : latest TLE of ISS selected by norad number
    cospar=2018-027A   : latest TLE of GSAT-6A selected by COSPAR ID
    ISS@oem            : latest OEM
    ISS@tle            : latest TLE
    ISS~               : one before last TLE
    ISS~~              : 2nd before last TLE
    ISS@oem~25         : 25th before last OEM
    ISS@oem^2018-12-25 : first OEM after the date
    ISS@tle?2018-12-25 : first tle before the date


Workspaces
^^^^^^^^^^

Workspaces allow the user to work on non-colluding databases. The default workspace is
*main*.
The companion command ``wspace`` allow to list, create or delete workspaces.
To actually use a workspace during a computation, you can use the ``SPACE_WORKSPACE``
environment variable, or directly in the command line, with the ``-w`` or ``--workspace`` options

.. code-block:: bash

    $ export SPACE_WORKSPACE=test  # all commands coming after will be in the 'test' workspace
    $ space passes TLS ISS
    $ space events ISS
    ...
    $ unset SPACE_WORKSPACE  # Disable the 'test' workspace, return to 'main'

    # The above is equivalent to
    $ space passes TLS ISS -w test
    $ space -w test events ISS

By default all workspaces are located in the ``.space/`` folder in the home directory.
It is possible to change the location with the ``SPACE_WORKSPACES_FOLDER`` environment variable.

.. _pipping:

Pipping commands
^^^^^^^^^^^^^^^^

It is possible to chain commands in order to feed a result from one to another.
In this case, the name of the satellite should be replaced by ``-`` in the second
command.

.. code-block:: shell

    # Compute the pass of Mars above a station
    space planet Mars | space passes TLS - -s 600s -g

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
