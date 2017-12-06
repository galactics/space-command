import yaml
from pathlib import Path
from beyond.config import config

__version__ = "0.1"


def load_config():
    """Load the config file and create missing directories
    """
    filepath = Path.home() / '.space/beyond.yaml'

    if filepath.exists():
        data = yaml.load(filepath.open())
        data['env']["folder"] = Path(data['env']["folder"])
        config.update(data)
    else:
        if not filepath.parent.exists():
            filepath.parent.mkdir()

        config.update({
            'env': {
                'folder': str(filepath.parent)
            },
            'eop': {
                'missing_policy': "pass",
            }
        })

        yaml.dump(config, filepath.open('w'))
