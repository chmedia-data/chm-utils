import importlib.metadata

from .logger import getLogger
from . import sls

__version__ = importlib.metadata.version("chm_utils")