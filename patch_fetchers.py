import re

with open("backend/app/services/garmin_sync.py", "r") as f:
    content = f.read()

new_fetchers = """
def _fetch_respiration_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_respiration_data"], date_str)

def _fetch_spo2_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_spo2_data"], date_str)

def _fetch_training_status_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_training_status"], date_str)
"""

content = content.replace("def _fetch_steps_payload", new_fetchers + "\n\ndef _fetch_steps_payload")

with open("backend/app/services/garmin_sync.py", "w") as f:
    f.write(content)
