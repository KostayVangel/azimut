FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /osnova

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]