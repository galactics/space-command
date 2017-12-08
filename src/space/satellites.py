
from .config import config
from .tle import TleDatabase, TleNotFound


class Satellite:

    def __init__(self, name, **kwargs):

        self.name = name
        self.norad_id = kwargs.get('norad_id')
        self.cospar_id = kwargs.get('cospar_id')
        self.emitters = kwargs.get('emitters', {})
        self.celestrak_file = kwargs.get('celestrak_file', '')

    def __repr__(self):
        return "<Satellite '%s'>" % self.name

    @classmethod
    def db(cls, to_save=None):
        if to_save is None:
            return config['satellites'].copy()
        else:
            config['satellites'] = to_save
            config.save()

    @property
    def default(self):
        return self.emitters[self.default_i]

    def add_emitter(self, emitter):
        self.emitter.append(emitter)

    def tle(self):
        return self.raw_tle().orbit()

    def raw_tle(self):
        return TleDatabase.get_last(norad_id=self.norad_id)

    @classmethod
    def get_all(cls):
        for name, sat in cls.db().items():
            if 'emitters' in sat:
                for k, v in sat['emitters'].items():
                    sat['emitters'][k] = Emitter(k, v['mode'], v['freq'], v['passband'])

            yield cls(name, **sat)

    @classmethod
    def get(cls, **kwargs):
        """
        Keyword Arguments:
            name (str): Name of the satellite
            norad_id (int): Catalog number of the satellite
            cospar_id (str): International designator of the satellite
        Return:
            Satellite:
        """

        if len(kwargs) > 1:
            raise ValueError("Only one criterion")

        criterion = tuple(kwargs.keys())[0]

        for x in cls.get_all():
            if getattr(x, criterion) == kwargs[criterion]:
                return x
        else:
            raise ValueError("No satellite found")

    def save(self):
        keys = ['name', 'mode', 'freq', 'passband']
        emitters = {}
        for em_name, em in self.emitters.items():
            emitters[em_name] = {x: getattr(em, x) for x in keys}

        try:
            complete_db = self.db()
        except FileNotFoundError:
            # In case of missing file, we deliver an empty database
            complete_db = {}

        complete_db[self.name] = {
            'norad_id': self.norad_id,
            'cospar_id': self.cospar_id,
            'emitters': emitters,
            'celestrak_file': self.celestrak_file
        }
        self.db(complete_db)


class Emitter:

    def __init__(self, name, mode, freq, passband):
        self.name = name
        self.mode = mode
        self.freq = int(freq)
        self.passband = int(passband)


def space_sats(*argv):
    """\
    Informations concerning the satellite database

    Usage:
        space-sats [create <mode> <selector> ...]

    Options:
      create      Create a new satellite with data extracted from the TLE database
      <mode>      Define the criterion on which the research will be done
                  Available modes are 'norad', 'cospar', 'name'
      <selector>  Depending on <mode>, this field should be the NORAD-ID,
                  COSPAR-ID, or name of the desired object.

    If no option is passed, the command will only display informations about
    the currently defined satellites
    """

    import sys
    from docopt import docopt
    from textwrap import dedent

    args = docopt(dedent(space_sats.__doc__), argv=argv)

    if args['create']:
        # Create a satellite object from the data available in the TLE database

        mode = args['<mode>']

        if mode in ("norad", "cospar"):
            mode += "_id"

        selector = " ".join(args['<selector>'])
        params = {mode: selector}
        try:
            tle = TleDatabase.get_last(**params)
        except TleNotFound as e:
            print(str(e))
            sys.exit(-1)

        if tle.kwargs['src'].startswith('celestrak'):
            source = tle.kwargs['src'].replace("celestrak, ", "")
        else:
            source = ""

        sat = Satellite(tle.name, **{
            'cospar_id': tle.cospar_id,
            'norad_id': tle.norad_id,
            'color': [0, 0, 0, 1],
            'celestrak_file': source
        })
        sat.save()
        print("Satellite created '{sat.name}' (norad_id={sat.norad_id}, cospar_id={sat.cospar_id})".format(sat=sat))
    else:
        for sat in Satellite.get_all():
            print(sat.name)
            print("-" * len(sat.name))

            print("Norad      %d" % sat.norad_id)
            print("Cospar     %s" % sat.cospar_id)

            tle = sat.raw_tle()
            print("TLE        {:%Y-%m-%d %H:%M:%S} from {}".format(tle.epoch, sat.celestrak_file))
            print("TLE name   %s" % tle.name)

            if sat.emitters:
                print("emitters:")
                for e in sat.emitters.values():
                    print("   {e.name} = {e.mode} {freq:7.3f} MHz {e.passband} Hz".format(
                        e=e,
                        freq=e.freq * 1e-6,
                    ))

            print()
