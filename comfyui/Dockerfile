FROM dustynv/l4t-pytorch:r36.4.0

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    aiohttp \
    einops \
    huggingface_hub[hf_transfer] \
    numpy>=1.25.0 \
    Pillow \
    psutil \
    pyyaml \
    safetensors>=0.4.2 \
    scipy \
    sentencepiece \
    tokenizers>=0.13.3 \
    torchaudio \
    torchsde \
    tqdm \
    transformers>=4.28.1

ENV HF_HUB_ENABLE_HF_TRANSFER 1

WORKDIR /app
RUN git clone https://github.com/comfyanonymous/ComfyUI /app

RUN huggingface-cli download \
    --repo-type=model \
    Lykon/DreamShaper \
    --include DreamShaper8_LCM.safetensors \
    --local-dir /app/models

CMD ["python3", "main.py"]
