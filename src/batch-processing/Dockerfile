FROM python:3.11-slim

WORKDIR /app

# Keep Python from writing .pyc files and disable pip cache
ENV PYTHONDONTWRITEBYTECODE=1 \
	PIP_NO_CACHE_DIR=1

# Copy application code
COPY app/ ./app/

# Default command: run batch jobs (placeholder)
CMD ["python", "-u", "app/batch_jobs.py"]
