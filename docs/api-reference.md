# RAGaaS API Reference

## Base URL

- Development: `http://localhost:8000`
- Production: `https://your-domain.com`

## Authentication

All API endpoints (except `/health`) require authentication via API key:

```
X-API-Key: your-api-key
```

## Endpoints

### Health Check

Check service health status.

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "api": true,
    "vector_store": true,
    "llm": true,
    "cache": true
  }
}
```

---

### Query

Query the RAG system with a question.

```
POST /api/v1/query
```

**Request Body:**
```json
{
  "question": "What is RAG?",
  "collection": "default",
  "top_k": 5,
  "temperature": 0.7,
  "max_tokens": 500,
  "stream": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `question` | string | Yes | - | The question to answer |
| `collection` | string | No | "default" | Collection to search |
| `top_k` | integer | No | 5 | Number of similar chunks to retrieve |
| `temperature` | float | No | 0.7 | LLM temperature (0.0-2.0) |
| `max_tokens` | integer | No | 500 | Maximum response tokens |
| `stream` | boolean | No | false | Enable streaming response |

**Response:**
```json
{
  "answer": "RAG (Retrieval Augmented Generation) is a technique...",
  "sources": [
    {
      "content": "RAG combines retrieval with generation...",
      "metadata": {
        "source": "rag-intro.pdf",
        "page": 1,
        "chunk_index": 0
      },
      "score": 0.92
    }
  ],
  "metadata": {
    "model": "gpt-4o-mini",
    "tokens_used": 450,
    "search_time_ms": 23,
    "llm_time_ms": 1200
  }
}
```

---

### Ingest Document

Upload and ingest a document.

```
POST /api/v1/ingest
```

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | file | Yes | Document file(s) to ingest |
| `collection` | string | No | Target collection (default: "default") |
| `metadata` | JSON | No | Additional metadata for documents |

**Supported Formats:**
- PDF (`.pdf`)
- Word (`.docx`)
- HTML (`.html`, `.htm`)
- Plain Text (`.txt`)
- Markdown (`.md`)

**Response:**
```json
{
  "status": "accepted",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "files": [
    {
      "filename": "document.pdf",
      "size": 102400,
      "status": "queued"
    }
  ]
}
```

---

### List Collections

List all available collections.

```
GET /api/v1/collections
```

**Response:**
```json
{
  "collections": [
    {
      "name": "default",
      "vectors_count": 1500,
      "points_count": 1500
    },
    {
      "name": "documents",
      "vectors_count": 3200,
      "points_count": 3200
    }
  ]
}
```

---

### Get Collection Info

Get detailed information about a collection.

```
GET /api/v1/collections/{collection_name}
```

**Response:**
```json
{
  "name": "default",
  "vectors_count": 1500,
  "points_count": 1500,
  "config": {
    "vector_size": 1536,
    "distance": "Cosine"
  },
  "status": "green"
}
```

---

### Delete Collection

Delete a collection and all its data.

```
DELETE /api/v1/collections/{collection_name}
```

**Response:**
```json
{
  "status": "deleted",
  "collection": "my-collection"
}
```

---

### Search (Vector Search Only)

Perform vector similarity search without LLM generation.

```
POST /api/v1/search
```

**Request Body:**
```json
{
  "query": "machine learning fundamentals",
  "collection": "default",
  "top_k": 10,
  "score_threshold": 0.7
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "chunk_001",
      "content": "Machine learning is a subset of AI...",
      "score": 0.95,
      "metadata": {
        "source": "ml-intro.pdf",
        "page": 5
      }
    }
  ],
  "search_time_ms": 15
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid API key |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Dependency down |

---

## Rate Limiting

- Default: 60 requests per minute per API key
- Headers returned:
  - `X-RateLimit-Limit`: Request limit
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Reset timestamp

---

## OpenAPI Specification

Interactive API documentation available at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`
