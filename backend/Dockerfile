# backend/Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your backend code
COPY . .

# Note: The actual start command will be defined in Render dashboard.
# For the web API: uvicorn main:app --host 0.0.0.0 --port $PORT
# For the worker: celery -A worker worker --loglevel=info