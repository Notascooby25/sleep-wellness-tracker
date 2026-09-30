from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
response = client.get("/reports/headache-summary?start_date=2026-08-01&end_date=2026-09-30")
print(response.status_code)
print(response.json())
