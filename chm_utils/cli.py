import argparse, os
import shlex
from . import sls

def get_version():
    import importlib.metadata
    return importlib.metadata.version("chm_utils")

def main():

    parser = argparse.ArgumentParser(description='CHM Utils CLI')
    parser.add_argument('command', type=str, choices=["sls.get_env", "version"])
    parser.add_argument(
        '-sep', 
        '--sls_env_path', 
        type=str, 
        help='Where in the sls config is the environment defined?'
    )

    args = parser.parse_args()
    if args.command and args.command.lower()  == 'sls.get_env':
        sls_env_path = args.sls_env_path or os.environ.get('SLS_ENV_PATH')
        env = sls.get_env(sls_env_path)
        print(' '.join([f'{k}={shlex.quote(v)}' for k, v in env.items()]))

    elif args.command == 'version':
        print(get_version())


if __name__ == "__main__":
    main()