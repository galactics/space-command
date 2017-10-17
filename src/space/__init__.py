from pathlib import Path
from beyond.config import config

__version__ = "0.1"


def init():
    """Load the config file and create missing directories
    """
    config_path = Path.home() / '.space'
    if not config_path.exists():
        print("creation of '%s'" % config_path)
        config_path.mkdir()

    conf_file = config_path / "beyond.conf"
    if not conf_file.exists():
        print("beyond.conf initialisation")

        (config_path / "tmp").mkdir()

        with conf_file.open('w') as f:
            f.write("[env]\neop_source = all")

        config.load(config_path)
    else:
        config.load(config_path)
