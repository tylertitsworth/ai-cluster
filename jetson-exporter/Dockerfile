FROM rbonghi/jetson_stats:latest

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt

COPY exporter.py /app/exporter.py

CMD ["python3", "exporter.py", "--port", "8000"]
