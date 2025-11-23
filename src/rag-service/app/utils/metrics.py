"""Prometheus metrics for monitoring."""

from prometheus_client import Counter, Gauge, Histogram, Info

# Application info
app_info = Info("rag_service", "RAG Service information")

# Request metrics
request_count = Counter(
    "rag_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)

request_latency = Histogram(
    "rag_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Query metrics
query_count = Counter(
    "rag_queries_total",
    "Total number of RAG queries",
    ["collection", "status"],
)

query_latency = Histogram(
    "rag_query_duration_seconds",
    "Query processing latency in seconds",
    ["collection"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

query_confidence = Histogram(
    "rag_query_confidence",
    "Distribution of query confidence scores",
    ["collection"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Document metrics
documents_ingested = Counter(
    "rag_documents_ingested_total",
    "Total number of documents ingested",
    ["collection"],
)

chunks_created = Counter(
    "rag_chunks_created_total",
    "Total number of chunks created",
    ["collection"],
)

# Vector store metrics
vector_search_count = Counter(
    "rag_vector_searches_total",
    "Total number of vector searches",
    ["collection", "status"],
)

vector_search_latency = Histogram(
    "rag_vector_search_duration_seconds",
    "Vector search latency in seconds",
    ["collection"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

# Embedding metrics
embedding_count = Counter(
    "rag_embeddings_generated_total",
    "Total number of embeddings generated",
    ["status"],
)

embedding_latency = Histogram(
    "rag_embedding_duration_seconds",
    "Embedding generation latency in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# LLM metrics
llm_requests = Counter(
    "rag_llm_requests_total",
    "Total number of LLM requests",
    ["model", "status"],
)

llm_latency = Histogram(
    "rag_llm_duration_seconds",
    "LLM response latency in seconds",
    ["model"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

llm_tokens = Counter(
    "rag_llm_tokens_total",
    "Total number of tokens used",
    ["model", "type"],  # type: prompt, completion
)

# Cache metrics
cache_hits = Counter(
    "rag_cache_hits_total",
    "Total number of cache hits",
    ["cache_type"],
)

cache_misses = Counter(
    "rag_cache_misses_total",
    "Total number of cache misses",
    ["cache_type"],
)

# Queue metrics
queue_messages_published = Counter(
    "rag_queue_messages_published_total",
    "Total number of messages published to queue",
    ["task_type"],
)

queue_messages_processed = Counter(
    "rag_queue_messages_processed_total",
    "Total number of messages processed from queue",
    ["task_type", "status"],
)

queue_depth = Gauge(
    "rag_queue_depth",
    "Current queue depth",
    ["queue_name"],
)

# Health metrics
service_health = Gauge(
    "rag_service_health",
    "Service health status (1=healthy, 0=unhealthy)",
    ["component"],
)


def record_request(method: str, endpoint: str, status: int, duration: float) -> None:
    """
    Record request metrics.

    Args:
        method: HTTP method
        endpoint: Request endpoint
        status: Response status code
        duration: Request duration in seconds
    """
    status_category = f"{status // 100}xx"
    request_count.labels(method=method, endpoint=endpoint, status=status_category).inc()
    request_latency.labels(method=method, endpoint=endpoint).observe(duration)


def record_query(
    collection: str,
    success: bool,
    duration: float,
    confidence: float,
) -> None:
    """
    Record query metrics.

    Args:
        collection: Collection queried
        success: Whether query succeeded
        duration: Query duration in seconds
        confidence: Confidence score
    """
    status = "success" if success else "error"
    query_count.labels(collection=collection, status=status).inc()
    query_latency.labels(collection=collection).observe(duration)
    if success:
        query_confidence.labels(collection=collection).observe(confidence)


def record_vector_search(collection: str, success: bool, duration: float) -> None:
    """
    Record vector search metrics.

    Args:
        collection: Collection searched
        success: Whether search succeeded
        duration: Search duration in seconds
    """
    status = "success" if success else "error"
    vector_search_count.labels(collection=collection, status=status).inc()
    vector_search_latency.labels(collection=collection).observe(duration)


def record_embedding(success: bool, duration: float) -> None:
    """
    Record embedding generation metrics.

    Args:
        success: Whether generation succeeded
        duration: Generation duration in seconds
    """
    status = "success" if success else "error"
    embedding_count.labels(status=status).inc()
    embedding_latency.observe(duration)


def record_llm_request(
    model: str,
    success: bool,
    duration: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """
    Record LLM request metrics.

    Args:
        model: Model used
        success: Whether request succeeded
        duration: Request duration in seconds
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
    """
    status = "success" if success else "error"
    llm_requests.labels(model=model, status=status).inc()
    llm_latency.labels(model=model).observe(duration)

    if prompt_tokens:
        llm_tokens.labels(model=model, type="prompt").inc(prompt_tokens)
    if completion_tokens:
        llm_tokens.labels(model=model, type="completion").inc(completion_tokens)


def record_cache(cache_type: str, hit: bool) -> None:
    """
    Record cache metrics.

    Args:
        cache_type: Type of cache (query, embedding)
        hit: Whether it was a cache hit
    """
    if hit:
        cache_hits.labels(cache_type=cache_type).inc()
    else:
        cache_misses.labels(cache_type=cache_type).inc()


def update_health(component: str, healthy: bool) -> None:
    """
    Update health status for a component.

    Args:
        component: Component name
        healthy: Whether component is healthy
    """
    service_health.labels(component=component).set(1 if healthy else 0)
