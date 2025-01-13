FROM dustynv/l4t-pytorch:r36.4.0

WORKDIR /root
ENV PYTHONPATH=/root
ENV FLYTE_SDK_RICH_TRACEBACKS=0

ARG DOCKER_IMAGE totalsundae/ai-cluster:jetson-flyte

RUN pip install --no-cache-dir flytekit \
    kubernetes \
    lightning \
    flytekitplugins-kfpytorch

RUN useradd -u 1000 flytekit \
    && chown flytekit: /root \
    && chown flytekit: /home

USER flytekit

ENV FLYTE_INTERNAL_IMAGE="$DOCKER_IMAGE"
