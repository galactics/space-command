Space Command
=============

The space command allows to compute the position of satellites and their passes above our head.

In order to do this, it uses the `beyond <https://github.com/galactics/beyond>`__ library.

Features
--------

* Retrieve orbits as TLE from celestrak
* Compute passes over a station for a list of satellites
* Ephemeris for rapid computation

Ideas
-----

Output ephem whereever

    $ space ephem ISS --frame EME2000 --stdout > <filename>

Folder as namespaces

    $ space init            # Create an empty space-command repo at ~/.space/default and link it
                            # with ~/.space/current
    $ space init <name>     # Create an empty space-command repo at ~/.space/<name>
    $ space switch <name>   # Change of repo by switching the ~/.space/current symbolic link to the
                            # name