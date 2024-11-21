test:
    docker run \
        -it \
        --rm \
        -v $HOME/.aws/credentials:/root/.aws/credentials \
        -e AWS_DEFAULT_REGION=eu-west-1 \
        -e AWS_PROFILE=chm-admin \
        -v .:/home/chm_utils/. \
        -w /home/chm_utils \
        --entrypoint /bin/bash \
        python:3 \
        -c "pip install -e .[test] && pytest"