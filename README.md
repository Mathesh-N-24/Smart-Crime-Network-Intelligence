# Smart-Crime-Network-Intelligence
Smart Crime Network Intelligence platform transforms scattered FIRs and evidence into an interconnected criminal network graph, enabling faster investigations through AI-powered analysis and a “What-If” simulator.It supports targeted disruption while preserving evidence integrity through cryptographic hashing and secure, 100% air-gapped processing.



🚀 How to Run

Requirements

Docker Desktop

Git (optional)

8 GB RAM or more recommended

Make sure Docker Desktop is running before starting CNAS.

1. Clone or Download

Clone the repository:

git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY

Or download the repository as a ZIP from GitHub and extract it.

2. Start CNAS

Run this command from the project root:

docker compose up --build -d

The first build may take several minutes.

3. Check Services

docker compose ps

The following services should be running:

neo4j
redis
backend
worker
frontend

4. Open the Dashboard

Open:

http://localhost:3000

5. Check Backend

Open:

http://localhost:8000/health

6. Test the Graph API

Open:

http://localhost:8000/graph?min_confidence=0

This should return the current graph nodes and relationships.

7. Open Neo4j

Open:

http://localhost:7474

Default development credentials:

Username: neo4j
Password: cnas_secure_pass123

Change these credentials before any real deployment.

🧪 Mock Test Data

A synthetic dataset is included at:

test-data/cnas_mock_case_project_nightfall.json

It contains fictional persons, accounts, devices, locations, relationships, evidence IDs, confidence scores, and timestamps.

Use it to test evidence ingestion and graph visualization.

🐳 Docker Services

Service

Purpose

Port

Frontend

CNAS dashboard

3000

Backend

FastAPI API

8000

Neo4j

Graph database + GDS

7474 / 7687

Redis

Celery message broker

6379

Worker

Background processing

—

🔧 Useful Commands

Start:

docker compose up -d

Build and start:

docker compose up --build -d

Check containers:

docker compose ps

View all logs:

docker compose logs -f

Backend logs:

docker compose logs -f backend

Worker logs:

docker compose logs -f worker

Frontend logs:

docker compose logs -f frontend

Neo4j logs:

docker compose logs -f neo4j

Restart:

docker compose restart

Stop:

docker compose stop

Rebuild after code changes:

docker compose up --build -d

Remove containers:

docker compose down

Do not use docker compose down -v unless you intentionally want to remove persistent Docker volumes containing Neo4j/evidence data.

🏗️ Architecture

                ┌──────────────────┐
                │    Next.js UI    │
                │  localhost:3000  │
                └────────┬─────────┘
                         │
                         ▼
                ┌──────────────────┐
                │   FastAPI API    │
                │  localhost:8000  │
                └──────┬─────┬─────┘
                       │     │
                 ┌─────▼─┐ ┌─▼──────┐
                 │ Neo4j │ │ Redis  │
                 │ + GDS │ │        │
                 └───────┘ └───┬────┘
                                │
                          ┌─────▼─────┐
                          │  Celery   │
                          │  Worker   │
                          └───────────┘

🔐 Security

CNAS is designed as a local/offline investigation prototype and supports:

Local processing

Cryptographic evidence hashing

Isolated Docker networking

Graph-based investigation

Offline deployment

The default configuration is intended for development/demo use and should be hardened before handling real investigation data.

📌 Project Status

CNAS is a prototype for cybersecurity research, investigation support, and demonstration.

It demonstrates:

Evidence ingestion

Criminal network visualization

Graph analytics

Entity relationships

Evidence integrity

Scenario analysis

Dockerized deployment
Entity relationships
Evidence integrity
Scenario analysis

Dockerized deployment
