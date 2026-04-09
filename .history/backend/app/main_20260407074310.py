import sys
import os
from fastapi import FastAPI

# Ensure the project root is on sys.path so "app.*" imports resolve inside the container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .routes import mood

app = FastAPI(title="Sleep Wellness Tracker")

# include the mood routes at root
app.include_router(mood.router, prefix="/mood")
from .routes import categories, activities

app.include_router(categories.router, prefix="/categories")
app.include_router(activities.router, prefix="/activities")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "sleep-wellness-tracker-backend"}

# test watcher

