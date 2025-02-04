test:
    docker build -t chm_utils . -f Dockerfile.test && \
        docker run \
        -it \
        -v $HOME/.aws/credentials:/root/.aws/credentials \
        --env AWS_DEFAULT_REGION=eu-west-1 \
        --env AWS_PROFILE=chm-admin \
        --env STAGE=test \
        chm_utils