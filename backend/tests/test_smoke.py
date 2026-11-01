"""Basic checks that the app starts, stays locked and can save an entry."""


def test_health_needs_no_login(client):
    assert client.get("/health").status_code == 200


def test_data_is_refused_without_login(client):
    assert client.get("/mood").status_code == 401
    assert client.post("/mood", json={"timestamp": "2026-01-01T09:00:00Z"}).status_code == 401
    assert client.get("/reports/headache-summary").status_code == 401


def test_wrong_password_is_refused(client):
    assert client.post("/auth/login", json={"password": "wrong"}).status_code == 401
    assert client.get("/mood").status_code == 401


def test_correct_password_opens_the_app(signed_in):
    assert signed_in.get("/mood").status_code == 200


def test_logging_out_locks_the_app_again(signed_in):
    assert signed_in.post("/auth/logout").status_code == 200
    assert signed_in.get("/mood").status_code == 401


def test_mood_entry_can_be_saved_and_read_back(signed_in):
    created = signed_in.post(
        "/mood",
        json={"mood_score": 7, "notes": "smoke test", "timestamp": "2026-01-02T09:00:00Z"},
    )
    assert created.status_code == 200
    entry = created.json()

    fetched = signed_in.get(f"/mood/{entry['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["mood_score"] == 7
    assert fetched.json()["notes"] == "smoke test"


def test_zero_mood_score_is_kept(signed_in):
    created = signed_in.post("/mood", json={"mood_score": 0, "timestamp": "2026-01-03T09:00:00Z"})
    assert created.status_code == 200
    assert signed_in.get(f"/mood/{created.json()['id']}").json()["mood_score"] == 0


def test_headache_summary_report_runs(signed_in):
    assert signed_in.get("/reports/headache-summary").status_code == 200
