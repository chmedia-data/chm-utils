import argparse, os
from . import sls


def main():

    parser = argparse.ArgumentParser(description='CHM Utils CLI')
    parser.add_argument('command', type=str, choices=["sls.get_env"])
    parser.add_argument(
        '-sep', 
        '--sls_env_path', 
        type=str, 
        help='Where in the sls config is the environment defined?'
    )

    args = parser.parse_args()
    if args.command and args.command.lower()  == 'sls.get_env':
        sls_env_path = args.sls_env_path or os.environ.get('SLS_ENV_PATH')
        print(sls.get_env(sls_env_path))


if __name__ == "__main__":
    main()