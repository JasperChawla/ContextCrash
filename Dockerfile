FROM python:3.11-slim

WORKDIR /app

# Node.js is needed only for the frontend build step
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Python deps — cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node deps — cached until package*.json changes
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm ci

# Full source copy, then build both layers
COPY . .
RUN cd frontend && npm run build
RUN pip install --no-cache-dir -e .

# DuckDB files land here; mount a volume in docker-compose for persistence
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
