from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
response = client.get("/reports/headache-summary")
print(response.status_code)
