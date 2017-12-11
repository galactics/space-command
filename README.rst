Space Command
=============

The space command allows to compute the position of satellites and their passes above our head.

In order to do this, it uses the `beyond <https://github.com/galactics/beyond>`__ library.

Installation
------------

    $ pip install space-command

Features
--------

**Retrieve orbits as TLE from celestrak**

.. code-block:: shell

    $ space tle get

**Compute passes over a station for a list of satellites**

.. code-block:: shell

    $ space passes <station> <sat>
