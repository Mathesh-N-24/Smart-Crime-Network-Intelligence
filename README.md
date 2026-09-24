# Smart-Crime-Network-Intelligence
Smart Crime Network Intelligence platform transforms scattered FIRs and evidence into an interconnected criminal network graph, enabling faster investigations through AI-powered analysis and a “What-If” simulator.It supports targeted disruption while preserving evidence integrity through cryptographic hashing and secure, 100% air-gapped processing.



🚀 How to Run

1. Requirements
  Install: Docker Desktop
  Git (optional)
  8 GB RAM or more recommended

Make sure Docker Desktop is running.

2. Clone the Repository

git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git cd YOUR_REPOSITORY
Or download the repository ZIP from GitHub and extract it.

3. Start 
Run this command from the folder containing docker-compose.yml:
docker compose up --build -d
Wait for the build and containers to finish starting.

4. Verify Everything Is Running
docker compose ps

You should have these five services running:

neo4j
redis
backend
worker
frontend

5. Open CNAS
Dashboard  : http://localhost:3000

Backend health: http://localhost:8000/health

Graph API: http://localhost:8000/graph?min_confidence=0

Neo4j Browser : http://localhost:7474

Neo4j development login:

Username: neo4j
Password: cnas_secure_pass123

The default password is for local/demo use only. Change it before any real deployment.

🧪 Test the System

A synthetic test dataset is included
It contains fictional:

Persons

Accounts

Devices

Locations

Relationships

Evidence records

Evidence IDs

Confidence scores

Timestamps



🏗️ Architecture

                         SCNT
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
       Next.js Frontend          FastAPI Backend
       localhost:3000            localhost:8000
                                       │
                         ┌─────────────┴─────────────┐
                         │                           │
                         ▼                           ▼
                      Neo4j                       Redis
                    Graph + GDS                Celery Broker
                                                     │
                                                     ▼
                                               Celery Worker


🔧 Common Commands

Start: docker compose up -d

Build + Start: docker compose up --build -d

Check Containers: docker compose ps

View All Logs: docker compose logs -f

Backend Logs: docker compose logs -f backend

Worker Logs: docker compose logs -f worker

Frontend Logs: docker compose logs -f frontend

Neo4j Logs: docker compose logs -f neo4j

Restart: docker compose restart

Stop: docker compose stop

Rebuild After Changes:docker compose up --build -d

Remove Containers:docker compose down

Do not use docker compose down -v unless you intentionally want to delete the persistent Docker volumes containing Neo4j/evidence data.


📌 Project Status

CNAS is a prototype for cybersecurity research, investigation support, and demonstration.

Demonstrated Capabilities

Evidence ingestion

Criminal network visualization

Entity relationships

Graph analytics

Evidence integrity

Scenario analysis

Dockerized deployment

