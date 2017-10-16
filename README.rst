Space Command
=============

The space command allows to compute the position of satellites and their passes above our head.

In order to do this, it uses the `beyond <https://github.com/galactics/beyond>`__ library.

Features
--------

* Retrieve orbits as TLE from celestrak
* Compute passes over a station for a list of satellites
* Ephemeris for rapid computation



One context by station

    $ space station TLS
    $ space chrono --sat ISS
    
    or

    $ space chrono --station TLS --sat ISS

Output ephem whereever

    $ space ephem ISS --frame EME2000 --stdout > <filename>

