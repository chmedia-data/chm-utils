import importlib.metadata
from . import sls
from . import logging

__logger__ = logging.getLogger('chm-utils')
__logger__.propagate = True
__logger__.removeHandler(logging.SlackHandler)

__version__ = importlib.metadata.version("chm_utils")