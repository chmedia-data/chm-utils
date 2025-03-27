import boto3, os, yaml, os, re


def get_dict_from_path(obj,path):
    if '.' in path:
        path_parts = path.split('.')
        root = path_parts[0]
        child = '.'.join(path_parts[1:])
        return get_dict_from_path(obj[root],child)
    else:
        return obj[path]


def get_config():

    cwd = os.getcwd()
    parent = os.path.abspath(os.path.join(cwd,os.pardir))
    src = os.path.join(cwd,'src')
    
    dirs_to_check = [cwd,src,parent]
    paths_to_check = [os.path.join(i,'serverless.yml') for i in dirs_to_check if i]
    if os.environ.get('SLS_CONFIG_PATH'):
        paths_to_check.append(os.path.join(os.environ.get('SLS_CONFIG_PATH')))

    paths_found = [i for i in paths_to_check if os.path.exists(i)]
    if len(paths_found) == 0:
        raise Exception('Serverless YML config could not be found!')

    with open(paths_found[0],'r') as f:
        config = yaml.safe_load(f.read())
    
    return config


def get_params(config,env_path):

    try:
        env = get_dict_from_path(config,env_path)
    except:
        raise Exception('No environment in serverless.yml found!')
    
    stage = os.environ.get('STAGE','local')
    params = []
    for k,v in env.items():

        if k == 'STAGE' or k in os.environ:
            continue

        if not isinstance(v,str):
            v = str(v)

        v = v.replace('${opt:stage}',stage)

        param_match  = re.search(r'\$\{ssm\:(.+?)\}', v)
        self_match  = re.search(r'\$\{self\:(.+?)\}', v)
        if param_match:
            params.append({'ssm_path':param_match.group(1), 'key':k})
        elif self_match:
            self_reference = self_match.group(1)
            new_value = re.sub(r'\$\{self\:(.+?)\}',get_dict_from_path(config,self_reference),v)
            params.append({'key':k,'value': new_value})
        else:
            params.append({'key':k,'value':v})
    
    return params


def resolve_ssm_params(ssm_params):
    return resolve_parameters(ssm_params, decrypt=False)


def get_ssm_params(ssm_param_paths):
    ssm_params = [{'ssm_path': path, 'key': path.split('/')[-1]} for path in ssm_param_paths]
    return resolve_parameters(ssm_params, decrypt=True)

def resolve_parameters(ssm_params, decrypt=False):
    env = {}
    ssm = boto3.client('ssm')
    for i in range(0, len(ssm_params), 10):
        batch = ssm_params[i:i+10]
        batch_names = [param['ssm_path'] for param in batch]
        batch_keys = {param['ssm_path']: param['key'] for param in batch}
        response = ssm.get_parameters(Names=batch_names, WithDecryption=decrypt)
        response_names = [p.get('Name', '') for p in response.get('Parameters', [])]
        missing_params = [name for name in batch_names if name not in response_names]
        if missing_params:
            raise Exception('Parameter(s) not found: ' + ','.join(missing_params))
        for p in response['Parameters']:
            key = batch_keys[p['Name']]
            env[key] = p['Value']
    return env

def get_env(env_path=None,config=None):

    config = config or get_config()
    env_path = env_path or os.environ.get('SLS_ENV_PATH','')
    params = get_params(config,env_path)

    env = {}
    for i in params:
        # if value already resolved, then no need to resolve from remote
        if 'value' in i:
            # we are not overwriting existing params (i.e. `.env.local` has precedence)
            if not i['key'] in os.environ:
                env[i['key']] = i['value']

    # resolve from remote
    ssm_params = [i for i in params if 'ssm_path' in i and not i['key'] in os.environ]
    ssm_env = resolve_ssm_params(ssm_params)
    env.update(ssm_env)
    
    return env


def set_env(env_path=None):
    env = get_env(env_path)
    for k,v in env.items():
        os.environ[k]=v