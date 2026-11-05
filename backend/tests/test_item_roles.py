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


def test_default_roles_follow_category():
    from app.services.item_roles import default_role_for_category

    assert default_role_for_category("Before Sleep") == "possible_cause"
    assert default_role_for_category("Lifestyle") == "possible_cause"
    assert default_role_for_category(" during sleep ") == "describes_night"
    assert default_role_for_category("Morning / Waking Feedback") == "describes_night"
    assert default_role_for_category("Headache Issues") == "symptom"
    assert default_role_for_category(None) == "possible_cause"


def test_ignored_activity_does_not_affect_effective_role():
    from app import models
    from app.services.item_roles import effective_role

    activity = models.Activity(name="x", ignore_in_reports=True, report_role=None)
    activity.category = models.Category(name="Before Sleep")
    assert effective_role(activity) == "possible_cause"


def test_owner_role_beats_default():
    from app import models
    from app.services.item_roles import effective_role

    activity = models.Activity(name="x", report_role="reaction", ignore_in_reports=False)
    activity.category = models.Category(name="Before Sleep")
    assert effective_role(activity) == "reaction"


def test_set_role_via_api_does_not_touch_ignore_flag(signed_in, clean_db):
    act = _make_activity(signed_in)
    url = f"/activities/{act['id']}/report-settings"

    body = signed_in.put(url, json={"report_role": "habit"}).json()
    assert body["report_role"] == "habit"
    assert body["ignore_in_reports"] is False

    body = signed_in.put(url, json={"report_role": None}).json()
    assert body["report_role"] is None
    assert body["ignore_in_reports"] is False


def test_hide_on_page_via_api(signed_in, clean_db):
    act = _make_activity(signed_in)
    url = f"/activities/{act['id']}/report-settings"
    signed_in.put(url, json={"report_role": "reaction"})

    body = signed_in.put(url, json={"hidden_pages": ["lifestyle_impact"]}).json()
    assert body["hidden_pages"] == ["lifestyle_impact"]
    assert body["report_role"] == "reaction"


def test_unknown_role_rejected(signed_in, clean_db):
    act = _make_activity(signed_in)
    response = signed_in.put(f"/activities/{act['id']}/report-settings", json={"report_role": "banana"})
    assert response.status_code == 422


def test_unexcluding_on_headache_page_does_not_touch_report_role(signed_in, clean_db):
    act = _make_activity(signed_in)
    signed_in.put(f"/activities/{act['id']}/report-settings", json={"report_role": "habit"})

    body = signed_in.put(f"/activities/{act['id']}", json={"ignore_in_reports": False}).json()
    assert body["ignore_in_reports"] is False
    assert body["report_role"] == "habit"


def test_unknown_hidden_page_rejected(signed_in, clean_db):
    act = _make_activity(signed_in)
    response = signed_in.put(f"/activities/{act['id']}/report-settings", json={"hidden_pages": ["x" * 5000]})
    assert response.status_code == 422


def test_table_wipe_refuses_non_test_database():
    from tests.conftest import _assert_throwaway_database

    import pytest

    with pytest.raises(RuntimeError):
        _assert_throwaway_database("postgresql://sleepuser:pw@db:5432/sleepdb")
    _assert_throwaway_database("postgresql://postgres:test@localhost:55432/sleeptest")
