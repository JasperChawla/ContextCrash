FROM python:3.11-slim

WORKDIR /app

# Install deps before copying code so layer is cached on dep changes only
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

# DuckDB files land here; mount a volume in docker-compose if you want persistence
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
