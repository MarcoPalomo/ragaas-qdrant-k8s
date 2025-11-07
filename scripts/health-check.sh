#!/bin/bash
set -e

echo "Vérification de l'état des services..."

kubectl get pods -n ragaas

echo "Vérification du endpoint API RAG..."
kubectl port-forward svc/rag-service 8080:8000 -n ragaas >/dev/null 2>&1 &
PID=$!
sleep 2
curl -f http://localhost:8080/health || (echo "API non disponible" && kill $PID && exit 1)
kill $PID

echo " Tous les services sont OK."
