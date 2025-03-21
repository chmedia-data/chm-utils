test PATH="":
    docker build -t chm_utils . -f Dockerfile.test && \
        docker run \
        -it \
        -v $(pwd)/tests/:/home/tests \
        -v $(pwd)/chm_utils:/home/chm_utils \
        -v $HOME/.aws/credentials:/root/.aws/credentials:ro \
        --env-file $HOME/.snowflake/.env \
        --env AWS_DEFAULT_REGION=eu-west-1 \
        --env AWS_PROFILE=chm-admin \
        --env STAGE=test \
        --env SKIP_PW_MFA_CREDENTIAL_TEST=true \
        --entrypoint /bin/bash \
        chm_utils -c "pip install -e . && pytest {{PATH}}"

testing_shell:
    docker build -t chm_utils . -f Dockerfile.test && \
        docker run \
        -it \
        -v $(pwd)/tests/:/home/tests \
        -v $(pwd)/chm_utils:/home/chm_utils \
        -v $HOME/.aws/credentials:/root/.aws/credentials:ro \
        --env-file $HOME/.snowflake/.env \
        --env AWS_DEFAULT_REGION=eu-west-1 \
        --env AWS_PROFILE=chm-admin \
        --env STAGE=test \
        chm_utils