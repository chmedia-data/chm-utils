import importlib.metadata
from . import sls
from . import logging

__logger__ = logging.getLogger('chm-utils', slack=False)
__logger__.propagate = True

__version__ = importlib.metadata.version("chm_utils")