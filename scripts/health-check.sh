#!/bin/bash
# Health check script for RAGaaS services
# Usage: ./health-check.sh [namespace]

set -euo pipefail

NAMESPACE="${1:-ragaas}"
EXIT_CODE=0

echo "=== RAGaaS Health Check ==="
echo "Namespace: ${NAMESPACE}"
echo "Timestamp: $(date -Iseconds)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_service() {
    local name=$1
    local selector=$2
    local port=$3
    local health_path=${4:-/health}

    echo -n "Checking ${name}... "

    # Check if pod exists and is running
    POD=$(kubectl get pods -n "${NAMESPACE}" -l "${selector}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    if [ -z "${POD}" ]; then
        echo -e "${RED}NO POD${NC}"
        return 1
    fi

    # Check pod status
    STATUS=$(kubectl get pod "${POD}" -n "${NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || true)
    if [ "${STATUS}" != "Running" ]; then
        echo -e "${YELLOW}${STATUS}${NC}"
        return 1
    fi

    # Check readiness
    READY=$(kubectl get pod "${POD}" -n "${NAMESPACE}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)
    if [ "${READY}" != "True" ]; then
        echo -e "${YELLOW}NOT READY${NC}"
        return 1
    fi

    echo -e "${GREEN}OK${NC} (${POD})"
    return 0
}

check_http_endpoint() {
    local name=$1
    local svc=$2
    local port=$3
    local path=${4:-/health}

    echo -n "  HTTP endpoint ${path}... "

    # Start port-forward
    kubectl port-forward -n "${NAMESPACE}" "svc/${svc}" "1${port}:${port}" &>/dev/null &
    PF_PID=$!
    sleep 2

    # Test endpoint
    if curl -sf "http://localhost:1${port}${path}" &>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        kill ${PF_PID} 2>/dev/null || true
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        kill ${PF_PID} 2>/dev/null || true
        return 1
    fi
}

echo "=== Pod Status ==="
check_service "RAG Service" "app.kubernetes.io/name=rag-service" "8000" || EXIT_CODE=1
check_service "Document Ingestor" "app.kubernetes.io/name=document-ingestor" "8001" || EXIT_CODE=1
check_service "Queue Worker" "app.kubernetes.io/name=queue-worker" "" || EXIT_CODE=1
check_service "Qdrant" "app.kubernetes.io/name=qdrant" "6333" || EXIT_CODE=1
check_service "Redis" "app.kubernetes.io/name=redis" "6379" || EXIT_CODE=1
check_service "RabbitMQ" "app.kubernetes.io/name=rabbitmq" "5672" || EXIT_CODE=1

echo ""
echo "=== HTTP Endpoints ==="
check_http_endpoint "RAG Service" "rag-service" "8000" "/health" || EXIT_CODE=1
check_http_endpoint "Qdrant" "qdrant" "6333" "/" || EXIT_CODE=1

echo ""
echo "=== Resource Usage ==="
kubectl top pods -n "${NAMESPACE}" 2>/dev/null || echo "Metrics not available (metrics-server not installed)"

echo ""
echo "=== Recent Events ==="
kubectl get events -n "${NAMESPACE}" --sort-by='.lastTimestamp' 2>/dev/null | tail -5 || true

echo ""
if [ ${EXIT_CODE} -eq 0 ]; then
    echo -e "=== ${GREEN}All services healthy${NC} ==="
else
    echo -e "=== ${RED}Some services have issues${NC} ==="
fi

exit ${EXIT_CODE}
