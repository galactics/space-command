
import yaml
from pathlib import Path

from beyond.config import config as beyond_config, Config as LegacyConfig


class SpaceConfig(LegacyConfig):

    filepath = Path.home() / '.space/config.yml'

    def __new__(cls, *args, **kwargs):

        if isinstance(cls._instance, LegacyConfig):
            cls._instance = None

        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)

        return cls._instance

    def load(self):
        """Load the config file and create missing directories
        """

        if self.filepath.exists():
            data = yaml.load(self.filepath.open())
            self.update(data)
        else:
            if not self.filepath.parent.exists():
                self.filepath.parent.mkdir()

            self.update({
                'beyond': {
                    'env': {
                        'folder': self.filepath.parent
                    },
                    'eop': {
                        'missing_policy': "pass",
                    }
                },
                'satellites': {
                    'ISS': {
                        'celestrak_file': 'visual.txt',
                        'cospar_id': '1998-067A',
                        'emitters': {},
                        'norad_id': 25544
                    },
                },
                'stations': {
                    'TLS': {
                        'latlonalt': (43.604482, 1.443962, 172.0),
                        'name': 'Toulouse',
                        'orientation': 'N',
                        'parent_frame': 'WGS84'
                    }
                }
            })
            self.save()

        beyond_config.update(self['beyond'])

    def save(self):
        yaml.dump(dict(self), self.filepath.open('w'), indent=4)


config = SpaceConfig()
