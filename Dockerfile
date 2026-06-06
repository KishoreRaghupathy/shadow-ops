# Dockerfile for Shadow-Ops Contract Intelligence Layer
FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for postgres client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Pre-install dependencies to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy codebase
COPY . .

# Expose ports for FastAPI (8000) and Streamlit (8501)
EXPOSE 8000
EXPOSE 8501

# Default execution starts the FastAPI REST service
CMD ["uvicorn", "src.bridges.api:app", "--host", "0.0.0.0", "--port", "8000"]
