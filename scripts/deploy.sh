#!/bin/bash
set -e

ENV=${1:-dev}

echo "Déploiement RAGaaS sur l'environnement '$ENV'..."
cd "$(dirname "$0")/.."

helmfile -e "$ENV" apply
echo "Déploiement terminé."
