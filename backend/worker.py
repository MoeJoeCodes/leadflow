# backend/worker.py
import os
import asyncio
from celery import Celery
from ig4 import start_scraper

# Connects to your Upstash Redis database
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "scraper_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

@celery_app.task(name="run_scraper_job")
def run_scraper_job(hashtags, limit):
    """This function is picked up by the Render worker and runs in the background"""
    # Create a fresh event loop for Playwright since Celery is synchronous
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # We assume cookies are stored in the DB or environment later, 
        # but for now, we'll pass None or a dummy path
        loop.run_until_complete(start_scraper(hashtags, "cookies.json", limit=limit, headless=True))
    except Exception as e:
        print(f"Scraper error: {e}")
    finally:
        loop.close()