"""Item roles decide which logged items count as possible causes in reports."""


def _make_activity(client, category_name="Before Sleep", name="Test item"):
    category = client.post("/categories/", json={"name": category_name}).json()
    activity = client.post("/activities/", json={"name": name, "category_id": category["id"]})
    assert activity.status_code == 200
    return activity.json()


def test_activity_has_report_columns(signed_in, clean_db):
    created = _make_activity(signed_in)
    fetched = signed_in.get(f"/activities/{created['id']}").json()
    assert fetched["report_role"] is None
    assert fetched["hidden_pages"] is None
