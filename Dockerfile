FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY backend ./backend
COPY attv ./attv
COPY ui ./ui

RUN pip install --no-cache-dir -r requirements.txt && pip install -e .

EXPOSE 8000 8501
