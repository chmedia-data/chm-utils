# CHM Utils

A custom python package with common utilities.
```
pip install git+https://github.com/chmedia-data/chm-utils
```

## Features
### Serverless Environment Resolution
With CLI:
```bash
chm_utils sls.get_env --sls_env_path functions.myfunction.environment
```

In python:
```python
from chm_utils import sls
sls.set_env(env_path='functions.myfunction.environment')
```


## Testing
```
pytest
```