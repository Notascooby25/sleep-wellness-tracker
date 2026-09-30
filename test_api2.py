from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
response = client.put("/activities/1", json={"ignore_in_reports": True})
print(response.status_code)
print(response.json())
