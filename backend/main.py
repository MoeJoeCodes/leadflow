import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from worker import run_scraper_job # Import your new celery task

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change this to your Vercel URL
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    hashtags: list[str]
    limit: int

@app.post("/scrape/start")
async def run_scrape(request: ScrapeRequest):
    # This pushes the job to Upstash Redis immediately and frees up the API
    run_scraper_job.delay(request.hashtags, request.limit)
    return {"message": "Scraper job added to queue. Check back later for results."}

@app.get("/leads")
async def get_leads():
    # Fetch directly from Supabase instead of reading local JSON files
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
    
    if not SUPABASE_URL:
        return []
        
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    try:
        # Fetch the latest 100 leads from the database
        response = supabase.table("leads").select("*").order("scraped_at", desc=True).limit(100).execute()
        return response.data
    except Exception as e:
        print(f"Error reading leads from DB: {e}")
        return []