FROM rayproject/ray:2.54.0-py312

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY actors.py tools.py serve.py llm.py utils.py workflow.py ./
COPY workflows/ workflows/
