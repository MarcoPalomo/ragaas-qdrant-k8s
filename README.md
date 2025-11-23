# RAGaaS - Retrieval Augmented Generation as a Service

A production-ready RAG service deployed on Kubernetes, featuring vector search (Qdrant), document ingestion pipeline, caching (Redis), message queuing (RabbitMQ), and comprehensive monitoring.

## Complete RAGaaS Architecture

```
ragaas-k8s/
├── src/                              # Application Source Code
│   ├── rag-service/                  # Main RAG API Service
│   │   ├── app/
│   │   │   ├── api/                  # FastAPI routes & models
│   │   │   ├── core/                 # Config & security
│   │   │   ├── services/             # Business logic (LLM, cache, queue)
│   │   │   └── utils/                # Logging & metrics
│   │   ├── tests/                    # Unit tests
│   │   ├── queue-worker/             # Background task worker
│   │   └── Dockerfile
│   ├── document-ingestor/            # Document processing service
│   │   ├── app/
│   │   │   ├── file_parsers.py       # PDF, DOCX, HTML parsers
│   │   │   ├── ingestor.py           # Chunking logic
│   │   │   ├── queue_consumer.py     # RabbitMQ consumer
│   │   │   └── storage.py            # MinIO client
│   │   └── Dockerfile
│   └── batch-processing/             # Batch reindexing jobs
│
├── k8s/                              # Kubernetes Manifests
│   ├── base/                         # Namespaces, ServiceAccounts, Secrets
│   ├── rag-service/                  # RAG API deployment
│   ├── document-ingestor/            # Ingestor deployment
│   ├── queue-worker/                 # Worker deployment
│   ├── qdrant/                       # Vector database
│   ├── redis/                        # Cache
│   ├── rabbitmq/                     # Message queue
│   ├── storage/                      # MinIO object storage
│   ├── ingress/                      # Ingress & TLS certificates
│   └── monitoring/                   # Prometheus & Grafana
│
├── config/                           # Configuration files
│   └── prometheus.yml                # Prometheus scrape configs
│
├── docker-compose.yml                # Local development
├── skaffold.yaml                     # Kubernetes development
├── Makefile                          # Build commands
└── .env.example                      # Environment template
```

### Components

| Component | Description | Technology |
|-----------|-------------|------------|
| **RAG Service** | Main API handling queries and similarity search | FastAPI, Python 3.11 |
| **Document Ingestor** | Processes and embeds documents | Python, pypdf, docx |
| **Queue Worker** | Background task processing | aio-pika |
| **Vector Store** | Efficient similarity search | Qdrant |
| **Cache** | Query result caching | Redis |
| **Message Queue** | Async task distribution | RabbitMQ |
| **Object Storage** | Raw document storage | MinIO |
| **Monitoring** | Metrics and dashboards | Prometheus, Grafana |

### Data Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Client     │────▶│  RAG Service │────▶│   Qdrant     │
│   Request    │     │   (FastAPI)  │     │ (Vectors)    │
└──────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────┴───────┐
                    ▼              ▼
              ┌──────────┐  ┌──────────────┐
              │  Redis   │  │   OpenAI     │
              │ (Cache)  │  │   (LLM)      │
              └──────────┘  └──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Document   │────▶│  RabbitMQ    │────▶│  Ingestor    │
│   Upload     │     │  (Queue)     │     │  Worker      │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                          ┌──────┴───────┐
                                          ▼              ▼
                                    ┌──────────┐  ┌──────────┐
                                    │  MinIO   │  │  Qdrant  │
                                    │ (Files)  │  │ (Vectors)│
                                    └──────────┘  └──────────┘
```

---

## Quick Start Commands

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- (Optional) Kubernetes cluster + Skaffold for K8s deployment

### First Time Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/ragaas-k8s
cd ragaas-k8s

# Initialize environment
make init

# Edit .env with your API keys
nano .env
```

### Development with Docker Compose

```bash
# Start all services
make dev

# Start with monitoring (Prometheus + Grafana)
make dev-monitor

# Start in background
make up

# Stop all services
make down

# View logs
make logs

# Check service health
make status

# Show all service URLs
make urls

# Clean up everything
make clean
```

### Kubernetes with Skaffold

```bash
# Deploy to local K8s with hot reload
make k8s-dev

# Deploy to K8s (one-time)
make k8s-run

# Show K8s resources status
make k8s-status

# Delete K8s resources
make k8s-delete

# Deploy to production
make k8s-prod
```

### Testing

```bash
# Run unit tests
make test

# Run tests with coverage
make test-cov

# Test API endpoints
make test-api

# Lint code
make lint

# Format code
make format
```

### Utility Commands

```bash
# Open shell in rag-service container
make shell

# Connect to Redis CLI
make redis-cli

# RabbitMQ management
make rabbitmq-cli
```

---

## Service Endpoints

### Development (Docker Compose)

| Service | URL | Credentials |
|---------|-----|-------------|
| RAG API | http://localhost:8000 | - |
| API Docs (Swagger) | http://localhost:8000/docs | - |
| Qdrant Dashboard | http://localhost:6333/dashboard | - |
| RabbitMQ Management | http://localhost:15672 | rabbitmq / rabbitmq |
| MinIO Console | http://localhost:9001 | minio / minio123 |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin / admin |

---

## API Usage

### Query Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "question": "What is RAG?",
    "collection": "default",
    "top_k": 5,
    "temperature": 0.7
  }'
```

### Document Ingestion

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "X-API-Key: your-api-key" \
  -F "files=@document.pdf" \
  -F "collection=default"
```

### List Collections

```bash
curl http://localhost:8000/api/v1/collections \
  -H "X-API-Key: your-api-key"
```

### Health Check

```bash
curl http://localhost:8000/health
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required
OPENAI_API_KEY=sk-your-openai-api-key

# Optional - API Authentication
RAG_SERVICE_TOKEN=your-api-token

# Infrastructure (defaults work for docker-compose)
QDRANT_API_KEY=
REDIS_PASSWORD=
RABBITMQ_USER=rabbitmq
RABBITMQ_PASSWORD=rabbitmq
MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=minio123

# Monitoring
GRAFANA_PASSWORD=admin
```

---

## Project Structure Details

### Source Code (`src/`)

```
src/
├── rag-service/                  # Main RAG API
│   ├── app/
│   │   ├── api/
│   │   │   ├── models.py         # Pydantic request/response models
│   │   │   └── routes.py         # API endpoints
│   │   ├── core/
│   │   │   ├── config.py         # Settings from environment
│   │   │   └── security.py       # API key auth, rate limiting
│   │   ├── services/
│   │   │   ├── vector_store.py   # Qdrant operations
│   │   │   ├── llm_service.py    # OpenAI integration
│   │   │   ├── cache_service.py  # Redis caching
│   │   │   ├── queue_service.py  # RabbitMQ publishing
│   │   │   └── document_processor.py  # Chunking
│   │   ├── utils/
│   │   │   ├── logger.py         # Structured JSON logging
│   │   │   └── metrics.py        # Prometheus metrics
│   │   └── main.py               # FastAPI application
│   ├── queue-worker/             # Background worker
│   ├── tests/                    # Unit tests
│   ├── Dockerfile
│   └── requirements.txt
│
├── document-ingestor/            # Document processing
│   ├── app/
│   │   ├── file_parsers.py       # PDF, DOCX, HTML, TXT parsers
│   │   ├── ingestor.py           # Document chunking
│   │   ├── queue_consumer.py     # RabbitMQ consumer
│   │   ├── storage.py            # MinIO operations
│   │   └── main.py               # Entry point
│   ├── Dockerfile
│   └── requirements.txt
│
└── batch-processing/             # Maintenance jobs
    └── app/
        └── batch_jobs.py         # Collection reindexing
```

---

## Monitoring

### Prometheus Metrics

The RAG service exposes metrics at `/metrics`:

- `rag_requests_total` - Total API requests
- `rag_query_duration_seconds` - Query latency
- `rag_vector_search_duration_seconds` - Vector search latency
- `rag_llm_duration_seconds` - LLM response time
- `rag_cache_hits_total` - Cache hit rate

### Grafana Dashboards

Access Grafana at http://localhost:3000 (when monitoring profile is enabled):

```bash
make dev-monitor
```

---

## Security

- API authentication via `X-API-Key` header
- Rate limiting (60 requests/minute per key)
- Non-root container execution
- Read-only root filesystems
- Network isolation via Kubernetes NetworkPolicies
- TLS certificates via cert-manager (production)
- Secrets management via Kubernetes Secrets

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
