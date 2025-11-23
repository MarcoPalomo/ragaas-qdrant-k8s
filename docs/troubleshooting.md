# Troubleshooting Guide

## Common Issues

### 1. Service Not Starting

#### Symptoms
- Pods stuck in `Pending` or `CrashLoopBackOff`
- Services not responding

#### Diagnosis
```bash
# Check pod status
kubectl get pods -n ragaas

# View pod details
kubectl describe pod <pod-name> -n ragaas

# Check logs
kubectl logs <pod-name> -n ragaas --tail=100

# Check events
kubectl get events -n ragaas --sort-by='.lastTimestamp' | tail -20
```

#### Common Causes & Solutions

**Insufficient Resources**
```bash
# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# Solution: Reduce resource requests or add nodes
```

**Image Pull Errors**
```bash
# Check image pull secret
kubectl get secret regcred -n ragaas

# Solution: Create/update image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io \
  --docker-username=<user> \
  --docker-password=<token> \
  -n ragaas
```

**Volume Mount Issues**
```bash
# Check PVC status
kubectl get pvc -n ragaas

# Solution: Check StorageClass exists
kubectl get sc
```

---

### 2. Connection Issues

#### RAG Service Can't Connect to Qdrant

```bash
# Test connectivity from RAG pod
kubectl exec -it deployment/rag-service -n ragaas -- \
  python -c "from qdrant_client import QdrantClient; c = QdrantClient('http://qdrant:6333'); print(c.get_collections())"

# Check Qdrant service
kubectl get svc qdrant -n ragaas
kubectl get endpoints qdrant -n ragaas
```

**Solutions:**
1. Verify Qdrant pod is running: `kubectl get pods -l app.kubernetes.io/name=qdrant -n ragaas`
2. Check service selector matches pod labels
3. Verify NetworkPolicy allows traffic

#### RAG Service Can't Connect to Redis

```bash
# Test Redis connectivity
kubectl exec -it deployment/rag-service -n ragaas -- \
  python -c "import redis; r = redis.Redis(host='redis', port=6379); print(r.ping())"
```

**Solutions:**
1. Check Redis password in secrets
2. Verify Redis pod is healthy

---

### 3. API Errors

#### 401 Unauthorized

```bash
# Verify API key exists in secrets
kubectl get secret ragaas-secrets -n ragaas -o jsonpath='{.data.RAG_SERVICE_TOKEN}' | base64 -d
```

**Solution:** Ensure `X-API-Key` header is set correctly

#### 429 Too Many Requests

Rate limit exceeded. Wait and retry, or increase limits in configuration.

#### 500 Internal Server Error

```bash
# Check RAG service logs
kubectl logs -l app.kubernetes.io/name=rag-service -n ragaas --tail=100

# Check if OpenAI API key is valid
kubectl get secret ragaas-secrets -n ragaas -o jsonpath='{.data.OPENAI_API_KEY}' | base64 -d
```

---

### 4. Performance Issues

#### Slow Query Response

```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics | grep rag_query_duration

# Check vector search performance
curl http://localhost:8000/metrics | grep rag_vector_search_duration
```

**Solutions:**
1. Increase Qdrant resources
2. Enable Redis caching
3. Reduce `top_k` parameter
4. Check network latency to OpenAI

#### High Memory Usage

```bash
# Check pod memory
kubectl top pods -n ragaas

# Check container limits
kubectl get deployment rag-service -n ragaas -o yaml | grep -A 5 resources
```

**Solutions:**
1. Increase memory limits
2. Reduce batch sizes
3. Check for memory leaks in logs

---

### 5. Ingestion Issues

#### Documents Not Being Processed

```bash
# Check RabbitMQ queue
kubectl exec -it rabbitmq-0 -n ragaas -- rabbitmqctl list_queues

# Check document-ingestor logs
kubectl logs -l app.kubernetes.io/name=document-ingestor -n ragaas --tail=100
```

**Solutions:**
1. Verify RabbitMQ is healthy
2. Check MinIO connectivity
3. Verify document format is supported

#### Embedding Generation Failing

```bash
# Check OpenAI API connectivity
kubectl exec -it deployment/document-ingestor -n ragaas -- \
  curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

---

### 6. Kubernetes-Specific Issues

#### HPA Not Scaling

```bash
# Check HPA status
kubectl get hpa -n ragaas
kubectl describe hpa rag-service -n ragaas

# Check metrics-server
kubectl get deployment metrics-server -n kube-system
```

#### PVC Stuck in Pending

```bash
# Check StorageClass
kubectl get sc

# Check PVC events
kubectl describe pvc <pvc-name> -n ragaas
```

---

## Diagnostic Commands

```bash
# Full cluster status
kubectl get all -n ragaas

# All logs from a service
kubectl logs -l app.kubernetes.io/name=rag-service -n ragaas --all-containers

# Execute into a pod
kubectl exec -it deployment/rag-service -n ragaas -- /bin/sh

# Port-forward for local testing
kubectl port-forward svc/rag-service 8000:8000 -n ragaas

# Network debugging pod
kubectl run debug --rm -it --image=nicolaka/netshoot -n ragaas -- /bin/bash
```

## Getting Help

1. Check the [FAQ](./faq.md)
2. Search [GitHub Issues](https://github.com/your-org/ragaas-k8s/issues)
3. Join our [Discord/Slack channel](#)
4. Open a new issue with diagnostic output
