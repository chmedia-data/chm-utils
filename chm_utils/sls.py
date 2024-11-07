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

    paths_to_check = ['../serverless.yml','serverless.yml',os.environ.get('SLS_CONFIG_PATH')]
    path = [i for i in paths_to_check if i and os.path.exists(i)]
    if len(path) == 0:
        raise Exception('Serverless YML config could not be found!')

    with open(path[0],'r') as f:
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

        if k == 'STAGE':
            continue

        if not isinstance(v,str):
            v = str(v)

        v = v.replace('${opt:stage}',stage)

        param_match  = re.search(r'\$\{ssm\:(.+?)\}', v)
        self_match  = re.search(r'\$\{self\:(.+?)\}', v)
        if param_match:
            params.append({'ssm_path':param_match.group(1), 'key':k})
        elif self_match:
            params.append({'key':k,'value':get_dict_from_path(config,self_match.group(1))})
        else:
            params.append({'key':k,'value':v})
    
    return params


def resolve_ssm_params(ssm_params):

    env = {}
    ssm = boto3.client('ssm')

    # batch requests
    for i in range(0,len(ssm_params),10):

        from_idx = i
        to_idx = min(i+10,len(ssm_params))
        batch = ssm_params[from_idx:to_idx]
        batch_names = [i['ssm_path'] for i in batch]
        batch_keys = {i['ssm_path']:i['key'] for i in batch}

        response = ssm.get_parameters(Names=batch_names)
        
        response_names = [i.get('Name','') for i in response.get('Parameters',[])]
        missing_params = [i for i in batch_names if not i in response_names]
        if len(missing_params) > 0:
            raise Exception('Parameter(s) not found: '+','.join(missing_params))
        
        for p in response['Parameters']:
            var_name = batch_keys[p['Name']]
            env[var_name] = p['Value']
        
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


def set_env(sls_env_path=None):
    env = get_env(sls_env_path)
    for k,v in env.items():
        os.environ[k]=v