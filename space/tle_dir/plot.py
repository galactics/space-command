import matplotlib.pyplot as plt

from beyond.constants import Earth


def plot(db, sats):
    fig = plt.figure() # figsize=[10,8])
    ax = fig.add_subplot(111)

    for sat in sats:
        tles = list(db.history(number=None, cospar_id=sat.cospar_id))

        color = next(ax._get_lines.prop_cycler)['color']

        epochs = [tle.epoch for tle in tles]
        perigee = [(tle.orbit().infos.rp - Earth.equatorial_radius)/1e3 for tle in tles]
        apogee = [(tle.orbit().infos.ra - Earth.equatorial_radius)/1e3 for tle in tles]

        ax.plot(
            epochs,
            perigee,
            label='{sat.norad_id} / {sat.cospar_id}'.format(sat=sat),
            color=color,
            marker = 'v',
            linestyle='--'
        )
        ax.plot(
            epochs, apogee,
            color=color,
            marker = '^',
            linestyle='--'
        )

    ax.set_xlabel('Epoch')
    ax.set_ylabel('Altitude / km')

    fig.autofmt_xdate()
    plt.legend()

    ax.grid()
    plt.show()
