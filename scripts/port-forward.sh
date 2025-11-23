#!/bin/bash
# Port forward script for local development
# Usage: ./port-forward.sh [namespace] [--stop]

set -euo pipefail

NAMESPACE="${1:-ragaas}"
ACTION="${2:-start}"
PID_FILE="/tmp/ragaas-port-forward.pids"

stop_forwards() {
    echo "Stopping port forwards..."
    if [ -f "${PID_FILE}" ]; then
        while read pid; do
            kill "${pid}" 2>/dev/null || true
        done < "${PID_FILE}"
        rm -f "${PID_FILE}"
        echo "All port forwards stopped"
    else
        echo "No active port forwards found"
    fi
}

start_forwards() {
    # Stop any existing forwards
    stop_forwards 2>/dev/null || true

    echo "=== RAGaaS Port Forwarding ==="
    echo "Namespace: ${NAMESPACE}"
    echo ""

    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        echo "Error: Cannot connect to Kubernetes cluster"
        exit 1
    fi

    # Create PID file
    > "${PID_FILE}"

    echo "Starting port forwards..."
    echo ""

    # RAG Service
    kubectl port-forward svc/rag-service 8000:8000 -n "${NAMESPACE}" &>/dev/null &
    echo $! >> "${PID_FILE}"

    # Qdrant
    kubectl port-forward svc/qdrant 6333:6333 -n "${NAMESPACE}" &>/dev/null &
    echo $! >> "${PID_FILE}"
    kubectl port-forward svc/qdrant 6334:6334 -n "${NAMESPACE}" &>/dev/null &
    echo $! >> "${PID_FILE}"

    # Redis
    kubectl port-forward svc/redis 6379:6379 -n "${NAMESPACE}" &>/dev/null &
    echo $! >> "${PID_FILE}"

    # RabbitMQ (AMQP + Management)
    kubectl port-forward svc/rabbitmq 5672:5672 -n "${NAMESPACE}" &>/dev/null &
    echo $! >> "${PID_FILE}"
    kubectl port-forward svc/rabbitmq 15672:15672 -n "${NAMESPACE}" &>/dev/null &
    echo $! >> "${PID_FILE}"

    # MinIO (API + Console)
    kubectl port-forward svc/minio 9000:9000 -n "${NAMESPACE}" &>/dev/null 2>&1 &
    echo $! >> "${PID_FILE}"
    kubectl port-forward svc/minio 9001:9001 -n "${NAMESPACE}" &>/dev/null 2>&1 &
    echo $! >> "${PID_FILE}"

    # Prometheus (if monitoring namespace)
    kubectl port-forward svc/prometheus-server 9090:9090 -n monitoring &>/dev/null 2>&1 &
    echo $! >> "${PID_FILE}"

    # Grafana (if monitoring namespace)
    kubectl port-forward svc/grafana 3000:3000 -n monitoring &>/dev/null 2>&1 &
    echo $! >> "${PID_FILE}"

    sleep 2

    echo "=== Available Services ==="
    echo ""
    echo "Application:"
    echo "  RAG Service API:     http://localhost:8000"
    echo "  RAG Service Docs:    http://localhost:8000/docs"
    echo ""
    echo "Databases:"
    echo "  Qdrant HTTP:         http://localhost:6333"
    echo "  Qdrant gRPC:         localhost:6334"
    echo "  Redis:               localhost:6379"
    echo ""
    echo "Messaging:"
    echo "  RabbitMQ AMQP:       localhost:5672"
    echo "  RabbitMQ Management: http://localhost:15672"
    echo ""
    echo "Storage:"
    echo "  MinIO API:           http://localhost:9000"
    echo "  MinIO Console:       http://localhost:9001"
    echo ""
    echo "Monitoring:"
    echo "  Prometheus:          http://localhost:9090"
    echo "  Grafana:             http://localhost:3000"
    echo ""
    echo "Run './port-forward.sh --stop' to stop all forwards"
    echo ""
    echo "Press Ctrl+C to stop..."

    # Wait for interrupt
    trap stop_forwards EXIT INT TERM
    wait
}

case "${ACTION}" in
    --stop|stop)
        stop_forwards
        ;;
    *)
        start_forwards
        ;;
esac
