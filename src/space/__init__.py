from pathlib import Path
from beyond.config import config

__version__ = "0.1"


def load_config():
    """Load the config file and create missing directories
    """
    try:
        config.read(Path.home() / '.space/beyond.conf')
    except FileNotFoundError:
        pass
