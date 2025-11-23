#!/bin/bash
# View logs for RAGaaS services
# Usage: ./logs.sh [service] [options]
#   Services: rag-service, document-ingestor, queue-worker, qdrant, redis, rabbitmq, all
#   Options:
#     -f, --follow     Stream logs in real-time
#     -n, --tail NUM   Number of lines to show (default: 100)
#     --since TIME     Show logs since timestamp (e.g., 1h, 30m, 2023-01-01)

set -euo pipefail

NAMESPACE="${RAGAAS_NAMESPACE:-ragaas}"
SERVICE="${1:-all}"
shift || true

# Parse options
FOLLOW=""
TAIL="100"
SINCE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW="-f"
            shift
            ;;
        -n|--tail)
            TAIL="$2"
            shift 2
            ;;
        --since)
            SINCE="--since=$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=== RAGaaS Logs ==="
echo "Namespace: ${NAMESPACE}"
echo "Service: ${SERVICE}"
echo ""

get_logs() {
    local selector=$1
    local name=$2

    echo "--- ${name} ---"
    kubectl logs -n "${NAMESPACE}" -l "${selector}" \
        --all-containers \
        --tail="${TAIL}" \
        ${FOLLOW} \
        ${SINCE} \
        2>/dev/null || echo "No pods found for ${name}"
    echo ""
}

case "${SERVICE}" in
    rag-service|rag)
        get_logs "app.kubernetes.io/name=rag-service" "RAG Service"
        ;;
    document-ingestor|ingestor)
        get_logs "app.kubernetes.io/name=document-ingestor" "Document Ingestor"
        ;;
    queue-worker|worker)
        get_logs "app.kubernetes.io/name=queue-worker" "Queue Worker"
        ;;
    qdrant)
        get_logs "app.kubernetes.io/name=qdrant" "Qdrant"
        ;;
    redis)
        get_logs "app.kubernetes.io/name=redis" "Redis"
        ;;
    rabbitmq)
        get_logs "app.kubernetes.io/name=rabbitmq" "RabbitMQ"
        ;;
    all)
        if [ -n "${FOLLOW}" ]; then
            echo "Note: --follow not supported with 'all'. Showing last ${TAIL} lines."
            FOLLOW=""
        fi
        get_logs "app.kubernetes.io/name=rag-service" "RAG Service"
        get_logs "app.kubernetes.io/name=document-ingestor" "Document Ingestor"
        get_logs "app.kubernetes.io/name=queue-worker" "Queue Worker"
        get_logs "app.kubernetes.io/name=qdrant" "Qdrant"
        get_logs "app.kubernetes.io/name=redis" "Redis"
        get_logs "app.kubernetes.io/name=rabbitmq" "RabbitMQ"
        ;;
    *)
        echo "Unknown service: ${SERVICE}"
        echo ""
        echo "Available services:"
        echo "  rag-service (rag)      - RAG API service"
        echo "  document-ingestor      - Document processing service"
        echo "  queue-worker (worker)  - Background task processor"
        echo "  qdrant                 - Vector database"
        echo "  redis                  - Cache"
        echo "  rabbitmq               - Message queue"
        echo "  all                    - All services"
        exit 1
        ;;
esac
