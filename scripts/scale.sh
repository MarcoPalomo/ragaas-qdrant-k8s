#!/bin/bash
# Scale RAGaaS services
# Usage: ./scale.sh [service] [replicas]
#   Services: rag-service, document-ingestor, queue-worker, all

set -euo pipefail

NAMESPACE="${RAGAAS_NAMESPACE:-ragaas}"
SERVICE="${1:-}"
REPLICAS="${2:-}"

usage() {
    echo "Usage: ./scale.sh <service> <replicas>"
    echo ""
    echo "Services:"
    echo "  rag-service         - RAG API service"
    echo "  document-ingestor   - Document processing service"
    echo "  queue-worker        - Background task processor"
    echo "  all                 - All application services"
    echo ""
    echo "Examples:"
    echo "  ./scale.sh rag-service 5    # Scale RAG service to 5 replicas"
    echo "  ./scale.sh all 3            # Scale all services to 3 replicas"
    echo "  ./scale.sh rag-service 0    # Scale down RAG service"
}

if [ -z "${SERVICE}" ] || [ -z "${REPLICAS}" ]; then
    usage
    exit 1
fi

if ! [[ "${REPLICAS}" =~ ^[0-9]+$ ]]; then
    echo "Error: Replicas must be a number"
    exit 1
fi

echo "=== RAGaaS Scaling ==="
echo "Namespace: ${NAMESPACE}"
echo "Service: ${SERVICE}"
echo "Replicas: ${REPLICAS}"
echo ""

scale_deployment() {
    local name=$1
    local label=$2

    echo "Scaling ${name} to ${REPLICAS} replicas..."

    DEPLOYMENT=$(kubectl get deployment -n "${NAMESPACE}" -l "${label}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

    if [ -z "${DEPLOYMENT}" ]; then
        echo "  Warning: Deployment not found for ${name}"
        return 1
    fi

    kubectl scale deployment "${DEPLOYMENT}" -n "${NAMESPACE}" --replicas="${REPLICAS}"
    echo "  OK - ${DEPLOYMENT} scaled"
}

case "${SERVICE}" in
    rag-service|rag)
        scale_deployment "RAG Service" "app.kubernetes.io/name=rag-service"
        ;;
    document-ingestor|ingestor)
        scale_deployment "Document Ingestor" "app.kubernetes.io/name=document-ingestor"
        ;;
    queue-worker|worker)
        scale_deployment "Queue Worker" "app.kubernetes.io/name=queue-worker"
        ;;
    all)
        scale_deployment "RAG Service" "app.kubernetes.io/name=rag-service"
        scale_deployment "Document Ingestor" "app.kubernetes.io/name=document-ingestor"
        scale_deployment "Queue Worker" "app.kubernetes.io/name=queue-worker"
        ;;
    *)
        echo "Error: Unknown service '${SERVICE}'"
        echo ""
        usage
        exit 1
        ;;
esac

echo ""
echo "Current replica counts:"
kubectl get deployments -n "${NAMESPACE}" -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,READY:.status.readyReplicas 2>/dev/null || true
