#!/bin/bash

set -e

PROJECT_DIR="/home/ubuntu/youtube-kafka-spark"

cd "$PROJECT_DIR"

echo "=== 7-day Delta cleanup started: $(date) ==="

echo "Stopping Spark..."
docker compose stop spark-streaming

echo "Running Delta cleanup..."
docker compose run --rm --no-deps spark-streaming \
    python /app/scripts/cleanup_delta.py

echo "Starting Spark..."
docker compose up -d spark-streaming

echo "=== 7-day Delta cleanup finished: $(date) ==="
