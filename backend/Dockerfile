FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for postgres and building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Pre-install CPU-only PyTorch to reduce download size from ~1GB to ~150MB
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

# The code will be mounted as a volume in docker-compose for dev, 
# but we also copy it here for completeness
COPY ./backend /app/

EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
