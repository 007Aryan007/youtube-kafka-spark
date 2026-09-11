# YouTube Kafka Spark Analytics

A real-time YouTube trending analytics pipeline built with Python, Kafka, Spark Structured Streaming, Delta Lake, Streamlit, Docker, and AWS EC2.

## Live Demo

Open the dashboard here: http://34.201.64.117:8501

## Overview

This project ingests live YouTube data through the YouTube Data API, streams it into Kafka, processes it with Apache Spark Structured Streaming, stores the results in Delta Lake, and visualizes the insights through a Streamlit dashboard.

## Architecture

```text
YouTube Data API
       ↓
Python Producer
       ↓
     Kafka
       ↓
Spark Structured Streaming
       ↓
   Delta Lake
       ↓
   Streamlit
       ↓
Analytics Dashboard
```

## Tech Stack

- Python — data ingestion and producer logic
- Apache Kafka — real-time event streaming
- Apache Spark — stream processing and transformation
- Delta Lake — reliable data storage
- Streamlit — interactive analytics dashboard
- Docker & Docker Compose — container orchestration
- AWS EC2 — deployment environment

## Key Features

- Real-time YouTube trending data ingestion
- Kafka-based streaming architecture
- Spark Structured Streaming data processing
- Delta Lake storage for transformed data
- Interactive Streamlit dashboard
- Category and region-based filtering
- Views and engagement analysis
- Predictive and recommendation-based analytics

## Prerequisites

Before running the project locally, ensure you have:

- Docker installed
- Docker Compose installed
- Git installed
- A valid YouTube Data API key

## Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/007Aryan007/youtube-kafka-spark.git
cd youtube-kafka-spark
```

### 2. Configure the API key

Create a `.env` file based on the example configuration and add your YouTube Data API key:

```bash
cp .env.example .env
```

Then add the following entry:

```env
YOUTUBE_API_KEY=your_api_key_here
```

### 3. Start the application

```bash
docker compose up -d --build
```

To confirm the containers are running:

```bash
docker compose ps
```

### 4. Open the dashboard

Visit:

```text
http://localhost:8501
```

## Verify the Pipeline

### Check Kafka topics

```bash
docker compose exec kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --list
```

Expected topic:

```text
youtube-data
```

### Check incoming messages

```bash
docker compose exec kafka kafka-console-consumer \
  --bootstrap-server kafka:9092 \
  --topic youtube-data \
  --from-beginning \
  --max-messages 5
```

### Check the Spark service logs

```bash
docker compose logs --tail=50 spark-streaming
```

## Services

| Service | Purpose |
| --- | --- |
| Zookeeper | Kafka coordination and metadata management |
| Kafka | Real-time message streaming |
| Producer | Collects YouTube data and publishes to Kafka |
| Spark Streaming | Processes Kafka streams and transforms the data |
| Dashboard | Displays analytical insights and visualizations |

## Deployment

The application is deployed on AWS EC2 using Docker Compose.

The Spark and dashboard containers share persistent storage to access the same Delta Lake data:

```yaml
volumes:
  - ./storage:/app/storage
```

This setup ensures that both services can read and write to the shared storage layer consistently.

## Notes

The pipeline is designed for continuous, near real-time analytics and can be used for monitoring trends, engagement patterns, and content performance across different categories and regions.