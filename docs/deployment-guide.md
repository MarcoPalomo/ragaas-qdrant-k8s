# Deployment Guide - RAG as a Service on Kubernetes

Complete guide for deploying the RAG service on Kubernetes.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Deployment Methods](#deployment-methods)
4. [Configuration](#configuration)
5. [Validation](#validation)
6. [Troubleshooting](#troubleshooting)

## Prerequisites

### 1. Kubernetes Cluster

Ensure you have a running Kubernetes cluster (v1.25+):

```bash
kubectl cluster-info
kubectl version --short
```

### 2. Required Tools

```bash
# Helm
helm version

# Helmfile
helmfile --version

# kubectl
kubectl version --client

# Optional: kustomize
kustomize version
```

### 3. Cluster Add-ons

Install these add-ons in your cluster:

#### Ingress Controller (nginx)

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.metrics.enabled=true \
  --set controller.podAnnotations."prometheus\.io/scrape"=true
```

#### Cert-Manager (for TLS)

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Wait for cert-manager to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/cert-manager -n cert-manager
```

#### Metrics Server (for HPA)

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

## Quick Start

### Method 1: Using Helmfile (Recommended)

```bash
# 1. Clone the repository
git clone <your-repo>
cd ragaas-k8s

# 2. Configure secrets
export OPENAI_API_KEY="sk-your-key-here"
export REDIS_PASSWORD="your-redis-password"
export RABBITMQ_PASSWORD="your-rabbitmq-password"

# 3. Update values for your environment
vim helmfile/values/production/common.yaml

# 4. Deploy everything
make install ENV=production

# 5. Check status
make status ENV=production
```

### Method 2: Using Kustomize

```bash
# 1. Update secrets
vim k8s/base/secrets.yaml

# 2. Deploy with kustomize
kubectl apply -k k8s/

# 3. Check deployment
kubectl get pods -n rag-system -w
```

### Method 3: Manual kubectl apply

```bash
# 1. Create namespace
kubectl apply -f k8s/base/namespace.yaml

# 2. Create secrets
kubectl apply -f k8s/base/secrets.yaml

# 3. Deploy infrastructure
kubectl apply -f k8s/redis/
kubectl apply -f k8s/rabbitmq/
kubectl apply -f k8s/qdrant/

# 4. Wait for infrastructure
kubectl wait --for=condition=ready pod -l app=redis -n rag-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=rabbitmq -n rag-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=qdrant -n rag-system --timeout=300s

# 5. Deploy application
kubectl apply -f k8s/rag-service/

# 6. Deploy ingress
kubectl apply -f k8s/ingress/
```

## Deployment Methods Detail

### Development Environment

```bash
# Using Helmfile
make install ENV=dev

# Configuration in: helmfile/values/dev/
# - Smaller resources
# - Single replicas
# - No TLS
# - Relaxed security
```

### Staging Environment

```bash
make install ENV=staging

# Configuration in: helmfile/values/staging/
# - Medium resources
# - 2 replicas
# - TLS enabled
# - Production-like setup
```

### Production Environment

```bash
# 1. Review the diff first
make diff ENV=production

# 2. Deploy
make install ENV=production

# Configuration in: helmfile/values/production/
# - Full resources
# - HA: 3+ replicas
# - TLS + Network policies
# - Monitoring enabled
# - Backups configured
```

## Configuration

### 1. Secrets Management

#### Option A: Kubernetes Secrets (Dev only)

```bash
# Create secrets manually
kubectl create secret generic rag-secrets \
  --from-literal=openai-api-key=sk-xxx \
  --from-literal=redis-password=xxx \
  --from-literal=rabbitmq-password=xxx \
  -n rag-system
```

#### Option B: External Secrets Operator (Production)

```bash
# 1. Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets \
  external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace

# 2. Configure SecretStore (example with AWS)
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: rag-system
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
EOF

# 3. Create ExternalSecret
kubectl apply -f k8s/base/external-secrets.yaml
```

#### Option C: Sealed Secrets

```bash
# 1. Install Sealed Secrets
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets \
  -n kube-system

# 2. Seal your secrets
kubectl create secret generic rag-secrets \
  --from-literal=openai-api-key=sk-xxx \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > sealed-secret.yaml

# 3. Apply sealed secret
kubectl apply -f sealed-secret.yaml
```

### 2. Environment-Specific Configuration

Edit the values files for each environment:

```yaml
# helmfile/values/production/rag-service.yaml
replicaCount: 5

resources:
  limits:
    cpu: 4000m
    memory: 8Gi
  requests:
    cpu: 1000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70

ingress:
  enabled: true
  hosts:
    - host: rag-api.yourcompany.com
  tls:
    - secretName: rag-api-tls
      hosts:
        - rag-api.yourcompany.com
```

### 3. Storage Configuration

Update storage classes if needed:

```yaml
# For each PVC, specify storageClassName
storageClassName: "fast-ssd"  # or gp3, premium-ssd, etc.
```

### 4. LLM Provider Configuration

Update in `k8s/rag-service/configmap.yaml`:

```yaml
data:
  LLM_PROVIDER: "openai"  # or "anthropic", "azure", "self-hosted"
  LLM_MODEL: "gpt-4-turbo-preview"
  EMBEDDING_MODEL: "text-embedding-3-small"
```

## Validation

### 1. Check Deployments

```bash
# All pods should be Running
kubectl get pods -n rag-system

# Expected output:
# NAME                           READY   STATUS    RESTARTS   AGE
# redis-0                        2/2     Running   0          5m
# rabbitmq-0                     1/1     Running   0          5m
# qdrant-0                       1/1     Running   0          5m
# rag-service-xxxx               1/1     Running   0          3m
# rag-service-yyyy               1/1     Running   0          3m
```

### 2. Check Services

```bash
kubectl get svc -n rag-system

# All services should have ClusterIP assigned
```

### 3. Check Ingress

```bash
kubectl get ingress -n rag-system

# Should show your domain and ADDRESS
```

### 4. Test Health Endpoints

```bash
# Port-forward
kubectl port-forward -n rag-system svc/rag-service 8000:80

# Test endpoints
curl http://localhost:8000/health/live
# {"status":"ok"}

curl http://localhost:8000/health/ready
# {"status":"ready","dependencies":{"redis":"ok","rabbitmq":"ok","qdrant":"ok"}}
```

### 5. Test API

```bash
# Query endpoint
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "top_k": 3
  }'
```

### 6. Check Metrics

```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# Should show various metrics like:
# http_requests_total
# http_request_duration_seconds
# cache_hits_total
```

## Post-Deployment Tasks

### 1. Initialize Qdrant Collections

```bash
# Run init script
kubectl exec -it -n rag-system qdrant-0 -- sh

# Or use the init script
kubectl apply -f k8s/jobs/init-collections.yaml
```

### 2. Configure Monitoring

```bash
# Install monitoring stack
make install-monitoring ENV=production

# Access Grafana
make port-forward-grafana

# Login: admin/admin (change immediately!)
# Import dashboards from monitoring/grafana/dashboards/
```

### 3. Setup Backups

```bash
# Configure backup cron jobs
kubectl apply -f k8s/cronjobs/backup-qdrant.yaml
kubectl apply -f k8s/cronjobs/backup-redis.yaml

# Test backup manually
kubectl create job --from=cronjob/backup-qdrant backup-test -n rag-system
```

### 4. Configure Alerts

```bash
# Alerts are configured in charts/monitoring/values.yaml
# Configure Slack webhook:
vim charts/monitoring/values.yaml
# Find alertmanager.config.receivers and add your Slack webhook
```

## Scaling

### Manual Scaling

```bash
# Scale RAG service
kubectl scale deployment rag-service --replicas=10 -n rag-system

# Or using make
make scale SERVICE=rag-service REPLICAS=10
```

### Auto-scaling (HPA)

The HPA is already configured. Monitor it:

```bash
kubectl get hpa -n rag-system -w

# Adjust HPA if needed
kubectl edit hpa rag-service-hpa -n rag-system
```

## Upgrades

### Rolling Update

```bash
# Update image tag
kubectl set image deployment/rag-service \
  rag-service=your-registry/rag-service:v1.2.0 \
  -n rag-system

# Watch rollout
kubectl rollout status deployment/rag-service -n rag-system
```

### Helmfile Upgrade

```bash
# Update values and sync
make upgrade ENV=production
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/rag-service -n rag-system

# Rollback to specific revision
kubectl rollout undo deployment/rag-service --to-revision=2 -n rag-system
```

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n rag-system

# Check logs
kubectl logs <pod-name> -n rag-system

# Check events
kubectl get events -n rag-system --sort-by='.lastTimestamp'
```

### Networking issues

```bash
# Test connectivity between pods
kubectl exec -it -n rag-system rag-service-xxx -- sh

# From inside pod, test:
nc -zv redis 6379
nc -zv rabbitmq 5672
nc -zv qdrant 6333
```

### Storage issues

```bash
# Check PVCs
kubectl get pvc -n rag-system

# Check PVs
kubectl get pv

# Describe PVC for events
kubectl describe pvc <pvc-name> -n rag-system
```

### Certificate issues

```bash
# Check certificates
kubectl get certificate -n rag-system

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager -f
```

## Clean Up

```bash
# Remove everything
make uninstall ENV=production

# Or manually
kubectl delete namespace rag-system

# Remove PVs (careful!)
kubectl delete pv -l app=rag-service
```

## Best Practices

1. **Always use Secrets Management** - Never commit secrets to git
2. **Test in Staging** - Always test deployments in staging first
3. **Monitor Resources** - Set up alerts for resource usage
4. **Regular Backups** - Automate backups for Qdrant and Redis
5. **Use Tags** - Tag all images with version numbers
6. **Document Changes** - Keep deployment history
7. **Security Scans** - Scan images for vulnerabilities
8. **Network Policies** - Enable in production
9. **Resource Limits** - Always set limits and requests
10. **Health Checks** - Properly configure all probes

## Next Steps

- [Configure Monitoring](./monitoring.md)
- [Setup CI/CD Pipeline](./cicd.md)
- [Performance Tuning](./performance-tuning.md)
- [Disaster Recovery](./disaster-recovery.md)