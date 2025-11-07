# RAGaaS - Retrieval Augmented Generation as a Service

A production-ready RAG service deployed on Kubernetes, featuring vector search (Qdrant), document ingestion pipeline, and batch processing capabilities.

## Architecture

### Components
- **RAG Service**: FastAPI service handling queries and vector similarity search
- **Document Ingestor**: Service for processing and embedding documents
- **Batch Processing**: Background jobs for maintenance (reindexing, etc.)
- **Vector Store**: Qdrant for efficient similarity search
- **Object Storage**: For raw document storage
- **Monitoring Stack**: Prometheus, Grafana, Loki

### Flow
1. Documents are uploaded via the ingestor or placed in object storage
2. Ingestor processes documents (chunking, embedding) and stores vectors in Qdrant
3. RAG service handles queries:
   - Similarity search in Qdrant
   - Context retrieval and LLM prompting
   - Response generation with sources

## Quick Start

### Prerequisites
- Kubernetes cluster (1.24+)
- Helm v3
- kubectl configured
- Docker for local development

### Local Development
```bash
# Clone the repository
git clone https://github.com/yourusername/ragaas-k8s
cd ragaas-k8s

# Install Python dependencies (use virtualenv)
python -m venv .venv
source .venv/bin/activate
pip install -r src/rag-service/requirements.txt

# Run Qdrant locally
docker run -d -p 6333:6333 qdrant/qdrant:latest

# Set environment variables
export OPENAI_API_KEY=your_key
export QDRANT_HOST=http://localhost:6333

# Run the RAG service
cd src/rag-service
uvicorn app.main:app --reload

# In another terminal, run the ingestor
cd src/document-ingestor
python -m app.main
```

### Kubernetes Deployment

1. **Set up Kubernetes**
   ```bash
   # Create namespace
   kubectl create namespace ragaas
   
   # Add Helm repositories
   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
   helm repo update
   ```

2. **Deploy Vector Store**
   ```bash
   # Deploy Qdrant
   helm upgrade --install qdrant ./charts/qdrant \
     --namespace ragaas \
     --create-namespace
   ```

3. **Deploy RAG Service**
   ```bash
   # Deploy main service and components
   helm upgrade --install ragaas ./charts/rag-service \
     --namespace ragaas \
     --set image.tag=latest \
     --values ./helmfile/values/dev/values.yaml
   ```

4. **Verify Installation**
   ```bash
   kubectl get all -n ragaas
   kubectl port-forward svc/ragaas 8000:8000 -n ragaas
   ```

## 📚 API Usage

### Query Endpoint
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is RAG?",
    "collection": "default",
    "top_k": 3
  }'
```

### Document Ingestion
```bash
curl -X POST http://localhost:8000/ingest \
  -F "files=@document.pdf" \
  -F "collection=default"
```

### Batch Processing
```bash
# Reindex a collection
cd src/batch-processing
python batch_jobs.py --collections mycollection --batch-size 100
```

## 🛠 Development

### Project Structure
```
ragaas-k8s/
├── charts/              # Helm charts
├── cicd/               # CI/CD configs and Dockerfiles
├── config/             # Application configs
├── data/               # Data & init scripts
├── docs/               # Documentation
├── helmfile/           # Helm deployments
├── k8s/                # Kubernetes manifests
├── monitoring/         # Monitoring configs
├── scripts/            # Utility scripts
└── src/                # Source code
    ├── batch-processing/
    ├── document-ingestor/
    └── rag-service/
```

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests with coverage
pytest src/rag-service/tests/ --cov=src/rag-service/app
```

### Building Images
```bash
# Build rag-service
docker build -t ragaas-service:latest -f cicd/Dockerfile.rag-service src/rag-service

# Build document-ingestor
docker build -t ragaas-ingestor:latest -f cicd/Dockerfile.ingestor src/document-ingestor
```

## Monitoring

The service includes:
- Prometheus metrics
- Grafana dashboards
- Loki for log aggregation

Access dashboards:
```bash
kubectl port-forward svc/grafana 3000:3000 -n monitoring
```

## Security

- API authentication via Bearer tokens
- RBAC for Kubernetes resources
- Network policies for service isolation
- Regular dependency scanning
- Image vulnerability scanning in CI

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
