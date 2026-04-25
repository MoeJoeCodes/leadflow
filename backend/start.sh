#!/bin/bash

# 1. Start the Celery worker in the background (the '&' symbol does this)
celery -A worker worker --loglevel=info &

# 2. Start the FastAPI web server in the foreground
uvicorn main:app --host 0.0.0.0 --port $PORT