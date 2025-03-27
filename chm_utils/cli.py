import argparse, os
import shlex
from . import sls
from . import __version__

def main():

    parser = argparse.ArgumentParser(description='CHM Utils CLI')
    parser.add_argument('command', type=str, choices=["sls.get_env", "version"])
    parser.add_argument(
        '-sep', 
        '--sls_env_path', 
        type=str, 
        help='Where in the sls config is the environment defined?'
    )
    parser.add_argument(
        '-of', 
        '--output-file', 
        type=str,
        default=None,
        help='Output to file instead of stdout'
    )

    args = parser.parse_args()
    if args.command and args.command.lower()  == 'sls.get_env':
        sls_env_path = args.sls_env_path or os.environ.get('SLS_ENV_PATH')
        env = sls.get_env(sls_env_path)
        
        # Generate env variable exports
        env_lines = []
        for k, v in env.items():
            env_lines.append(f"export {k}={shlex.quote(v)}")
        
        output = "\n".join(env_lines)
        
        # Either write to file or print to stdout
        if args.output_file is not None:
            with open(args.output_file, 'w') as f:
                f.write(output)
        else:
            print(output)

    elif args.command == 'version':
        print("`chm_utils` version: "+__version__)


if __name__ == "__main__":
    main()