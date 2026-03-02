FROM python:3.11-slim

# System deps for PyMuPDF, PaddleOCR, psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    # Patch qdrant-client 1.17.0: grpcio 1.62 EnumTypeWrapper lacks __or__ for union annotations
    sed -i '1s/^/from __future__ import annotations\n/' \
        /usr/local/lib/python3.11/site-packages/qdrant_client/uploader/grpc_uploader.py

# Install Playwright browsers (run manually when crawlers are needed: playwright install chromium)
# RUN playwright install chromium && playwright install-deps chromium

# Copy source
COPY . .

# Default command (overridden in docker-compose for specific services)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
