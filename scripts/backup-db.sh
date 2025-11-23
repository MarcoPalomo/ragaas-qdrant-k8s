#!/bin/bash
# Backup script for RAGaaS databases
# Usage: ./backup-db.sh [namespace]

set -euo pipefail

NAMESPACE="${1:-ragaas}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/../data/backups/$(date +%Y-%m-%d_%H-%M-%S)"

echo "=== RAGaaS Database Backup ==="
echo "Namespace: ${NAMESPACE}"
echo "Backup directory: ${BACKUP_DIR}"
echo ""

mkdir -p "${BACKUP_DIR}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed"
    exit 1
fi

# Check namespace exists
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo "Error: Namespace '${NAMESPACE}' does not exist"
    exit 1
fi

# Backup Qdrant
echo "[1/3] Backing up Qdrant vector database..."
QDRANT_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=qdrant -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "${QDRANT_POD}" ]; then
    kubectl exec -n "${NAMESPACE}" "${QDRANT_POD}" -- tar -czf - /qdrant/storage > "${BACKUP_DIR}/qdrant-backup.tar.gz" 2>/dev/null
    echo "  Qdrant backup completed: $(du -h "${BACKUP_DIR}/qdrant-backup.tar.gz" | cut -f1)"
else
    echo "  Warning: Qdrant pod not found, skipping..."
fi

# Backup Redis (RDB dump)
echo "[2/3] Backing up Redis cache..."
REDIS_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "${REDIS_POD}" ]; then
    kubectl exec -n "${NAMESPACE}" "${REDIS_POD}" -- redis-cli BGSAVE &>/dev/null || true
    sleep 2
    kubectl exec -n "${NAMESPACE}" "${REDIS_POD}" -- cat /data/dump.rdb > "${BACKUP_DIR}/redis-backup.rdb" 2>/dev/null || true
    if [ -s "${BACKUP_DIR}/redis-backup.rdb" ]; then
        echo "  Redis backup completed: $(du -h "${BACKUP_DIR}/redis-backup.rdb" | cut -f1)"
    else
        echo "  Warning: Redis backup empty or failed"
        rm -f "${BACKUP_DIR}/redis-backup.rdb"
    fi
else
    echo "  Warning: Redis pod not found, skipping..."
fi

# Export Qdrant collections metadata via API
echo "[3/3] Exporting Qdrant collections metadata..."
if kubectl port-forward -n "${NAMESPACE}" svc/qdrant 16333:6333 &>/dev/null & then
    PF_PID=$!
    sleep 2
    curl -s http://localhost:16333/collections 2>/dev/null > "${BACKUP_DIR}/qdrant-collections.json" || true
    kill ${PF_PID} 2>/dev/null || true
    if [ -s "${BACKUP_DIR}/qdrant-collections.json" ]; then
        echo "  Collections metadata exported"
    fi
fi

# Create backup manifest
cat > "${BACKUP_DIR}/manifest.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "namespace": "${NAMESPACE}",
  "components": {
    "qdrant": $([ -f "${BACKUP_DIR}/qdrant-backup.tar.gz" ] && echo "true" || echo "false"),
    "redis": $([ -f "${BACKUP_DIR}/redis-backup.rdb" ] && echo "true" || echo "false")
  }
}
EOF

echo ""
echo "=== Backup Complete ==="
echo "Location: ${BACKUP_DIR}"
echo "Files:"
ls -lh "${BACKUP_DIR}/"
