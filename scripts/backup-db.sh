#!/bin/bash
set -e

BACKUP_DIR="data/backups/$(date +%Y-%m-%d_%H-%M)"
mkdir -p "$BACKUP_DIR"

echo "Sauvegarde Qdrant..."
kubectl exec -n ragaas deploy/qdrant -- tar -czf - /qdrant/storage > "$BACKUP_DIR/qdrant-backup.tar.gz"

echo "Sauvegarde terminée : $BACKUP_DIR"
