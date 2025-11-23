#!/bin/bash
# Deploy RAGaaS to Kubernetes using Helmfile
# Usage: ./deploy.sh [environment] [options]
#   Environments: dev, staging, production
#   Options:
#     --dry-run    Show what would be deployed without applying
#     --diff       Show differences before applying
#     --sync       Only sync (no diff)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/.."
ENV="${1:-dev}"
OPTION="${2:-}"

echo "=== RAGaaS Deployment ==="
echo "Environment: ${ENV}"
echo "Project dir: ${PROJECT_DIR}"
echo ""

# Validate environment
if [[ ! "${ENV}" =~ ^(dev|staging|production)$ ]]; then
    echo "Error: Invalid environment '${ENV}'"
    echo "Valid environments: dev, staging, production"
    exit 1
fi

# Check dependencies
for cmd in kubectl helm helmfile; do
    if ! command -v ${cmd} &> /dev/null; then
        echo "Error: ${cmd} is not installed"
        exit 1
    fi
done

# Check cluster connectivity
echo "Checking cluster connectivity..."
if ! kubectl cluster-info &> /dev/null; then
    echo "Error: Cannot connect to Kubernetes cluster"
    echo "Please check your kubeconfig"
    exit 1
fi
echo "Cluster: $(kubectl config current-context)"
echo ""

cd "${PROJECT_DIR}/helmfile"

# Handle options
case "${OPTION}" in
    --dry-run)
        echo "Dry run mode - showing what would be deployed..."
        helmfile -e "${ENV}" template
        ;;
    --diff)
        echo "Showing differences..."
        helmfile -e "${ENV}" diff
        echo ""
        read -p "Apply these changes? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            helmfile -e "${ENV}" apply
        else
            echo "Deployment cancelled"
            exit 0
        fi
        ;;
    --sync)
        echo "Syncing releases..."
        helmfile -e "${ENV}" sync
        ;;
    *)
        echo "Deploying to ${ENV}..."
        helmfile -e "${ENV}" apply
        ;;
esac

echo ""
echo "=== Deployment Complete ==="

# Show status
echo ""
echo "Checking deployment status..."
kubectl get pods -n ragaas -o wide 2>/dev/null || true

echo ""
echo "Services:"
kubectl get svc -n ragaas 2>/dev/null || true
