FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake Chroma's local embedding model into the image so the first research request doesn't download it.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as D; D()(['warm up'])"

COPY app ./app
COPY scripts ./scripts
COPY seed ./seed

ENV DATA_DIR=/data
RUN mkdir -p /data
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
