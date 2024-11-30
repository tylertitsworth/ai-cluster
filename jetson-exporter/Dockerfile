FROM dustynv/cuda-python:builder-r36.2.0

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt

COPY exporter.py /app/exporter.py

CMD ["python", "exporter.py", "--port", "8000"]
