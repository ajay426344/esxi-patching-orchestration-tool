FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    openssh-client \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/patches

EXPOSE 8000

# Direct command - no start.sh needed
CMD ["sh", "-c", "python database.py && uvicorn app:app --host 0.0.0.0 --port 8000 --reload"]
