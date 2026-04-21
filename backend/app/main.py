from fastapi import FastAPI
from .routes import mood, categories, activities, garmin

app = FastAPI()

# Routers ALREADY have prefixes inside their files.
# Do NOT add prefixes here.

app.include_router(mood.router)
app.include_router(categories.router)
app.include_router(activities.router)
app.include_router(garmin.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
