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

.. code-block:: shell

    # Retrieve orbits as TLE from celestrak
    $ space tle get

    # Compute passes over a station for a list of satellites
    $ space passes <station> <sat>

    # Animated map showing position of a satellite (e.g. the ISS)
    $ space map ISS

    # Compute Sun rising and setting times
    $ space sun <station>

    # Compute Moon rising and setting times and display moon phase
    $ space moon <station> --graph
