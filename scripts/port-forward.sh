#!/bin/bash

echo " Ouverture des ports pour dev local..."
kubectl port-forward svc/rag-service 8080:8000 -n ragaas &
kubectl port-forward svc/qdrant 6333:6333 -n ragaas &
kubectl port-forward svc/redis 6379:6379 -n ragaas &
kubectl port-forward svc/rabbitmq 15672:15672 -n ragaas &

echo " Accès :"
echo " - RAG Service : http://localhost:8080"
echo " - Qdrant : http://localhost:6333"
echo " - Redis : localhost:6379"
echo " - RabbitMQ : http://localhost:15672"
