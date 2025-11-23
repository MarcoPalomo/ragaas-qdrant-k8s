# RAGaaS Makefile
.PHONY: help dev up down build test clean logs deploy

SHELL := /bin/bash
NAMESPACE := ragaas

# Colors
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m

# Default target
help:
	@echo "$(GREEN)RAGaaS - Retrieval Augmented Generation as a Service$(NC)"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make init           - First time setup (create .env from example)"
	@echo "  make dev            - Start development environment with docker compose"
	@echo "  make dev-monitor    - Start with monitoring (Prometheus + Grafana)"
	@echo "  make up             - Start all services in background"
	@echo "  make down           - Stop all services"
	@echo "  make build          - Build all Docker images"
	@echo "  make logs           - Tail logs from all services"
	@echo "  make clean          - Remove all containers and volumes"
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@echo "  make test           - Run all tests"
	@echo "  make test-cov       - Run tests with coverage"
	@echo ""
	@echo "$(YELLOW)Kubernetes (Skaffold):$(NC)"
	@echo "  make k8s-dev        - Deploy to local Kubernetes (skaffold dev)"
	@echo "  make k8s-run        - Deploy to Kubernetes (skaffold run)"
	@echo "  make k8s-delete     - Delete Kubernetes resources"
	@echo "  make k8s-status     - Show Kubernetes resources status"
	@echo ""
	@echo "$(YELLOW)Utilities:$(NC)"
	@echo "  make shell          - Open shell in rag-service container"
	@echo "  make redis-cli      - Connect to Redis CLI"
	@echo "  make status         - Show status of all services"

# ===================
# Initialization
# ===================
init:
	@echo "$(GREEN)Creating .env file from example...$(NC)"
	@cp -n .env.example .env 2>/dev/null || echo ".env already exists"
	@echo "$(GREEN)Building images...$(NC)"
	docker compose build
	@echo ""
	@echo "$(GREEN)Setup complete!$(NC)"
	@echo "Edit .env with your API keys, then run: make dev"

# ===================
# Development
# ===================
dev:
	docker compose up --build

dev-monitor:
	docker compose --profile monitoring up --build

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache

rebuild: down build up

logs:
	docker compose logs -f

logs-service:
	docker compose logs -f $(SERVICE)

clean:
	docker compose down -v --rmi local
	docker system prune -f

# ===================
# Testing
# ===================
test:
	cd src/rag-service && python -m pytest tests/ -v

test-cov:
	cd src/rag-service && python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term

lint:
	cd src/rag-service && python -m flake8 app/
	cd src/rag-service && python -m mypy app/

format:
	cd src/rag-service && python -m black app/ tests/
	cd src/rag-service && python -m isort app/ tests/

# ===================
# Kubernetes with Skaffold
# ===================
k8s-dev:
	skaffold dev --profile=local --port-forward

k8s-run:
	skaffold run --profile=local

k8s-delete:
	skaffold delete --profile=local
	kubectl delete namespace $(NAMESPACE) --ignore-not-found

k8s-status:
	@echo "$(GREEN)=== Pods ===$(NC)"
	kubectl get pods -n $(NAMESPACE)
	@echo ""
	@echo "$(GREEN)=== Services ===$(NC)"
	kubectl get svc -n $(NAMESPACE)
	@echo ""
	@echo "$(GREEN)=== PVCs ===$(NC)"
	kubectl get pvc -n $(NAMESPACE)

k8s-logs:
	kubectl logs -f -n $(NAMESPACE) -l app.kubernetes.io/name=$(SERVICE) --tail=100

k8s-prod:
	skaffold run --profile=prod

# ===================
# Utilities
# ===================
shell:
	docker compose exec rag-service /bin/sh

redis-cli:
	docker compose exec redis redis-cli

rabbitmq-cli:
	docker compose exec rabbitmq rabbitmqctl

status:
	@echo "$(GREEN)=== Docker Containers ===$(NC)"
	@docker compose ps
	@echo ""
	@echo "$(GREEN)=== Service Health ===$(NC)"
	@curl -s http://localhost:8000/health 2>/dev/null | python -m json.tool 2>/dev/null || echo "RAG Service: Not running"
	@echo ""
	@curl -s http://localhost:6333/readyz 2>/dev/null && echo "Qdrant: Running" || echo "Qdrant: Not running"
	@docker compose exec -T redis redis-cli ping 2>/dev/null && echo "Redis: Running" || echo "Redis: Not running"

# Service URLs
urls:
	@echo "$(GREEN)=== Service URLs ===$(NC)"
	@echo "RAG Service API:    http://localhost:8000"
	@echo "RAG Service Docs:   http://localhost:8000/docs"
	@echo "Qdrant Dashboard:   http://localhost:6333/dashboard"
	@echo "RabbitMQ Mgmt:      http://localhost:15672 (rabbitmq/rabbitmq)"
	@echo "MinIO Console:      http://localhost:9001 (minio/minio123)"
	@echo "Prometheus:         http://localhost:9090 (if monitoring enabled)"
	@echo "Grafana:            http://localhost:3000 (admin/admin)"

# API Testing
test-api:
	@echo "$(GREEN)Testing RAG Service API...$(NC)"
	@echo "Health check:"
	@curl -s http://localhost:8000/health | python -m json.tool
	@echo ""
	@echo "Query test (requires API key if configured):"
	@curl -s -X POST http://localhost:8000/api/v1/query \
		-H "Content-Type: application/json" \
		-d '{"question": "What is RAG?", "collection": "default"}' | python -m json.tool || true

# Default
.DEFAULT_GOAL := help
