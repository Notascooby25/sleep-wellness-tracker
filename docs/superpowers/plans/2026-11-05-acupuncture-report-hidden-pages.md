# Fix: Acupuncture Report Hidden Pages & Left Out Items Deletion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two related issues on the Acupuncture & Symptom Report page: (1) allow hiding an activity on the page by adding `"acupuncture_report"` to the backend `hidden_pages` schema, and (2) ensure default morning/night feedback items (like "Woke up tired") do not clutter the "Left out of this page" chips and that clicking × on left-out items successfully deletes/restores them.

**Architecture:** 
1. In `backend/app/schemas.py`, expand `ActivityReportSettings.hidden_pages` to accept `"acupuncture_report"` in addition to `"lifestyle_impact"` and `"headache_report"`.
2. In `backend/app/services/symptom_report.py`, only include `describes_night` activities in `left_out` if `role_was_set_by_owner(primary)` (matching `habit` and matching `lifestyle_impact.py`), so category-default morning items don't falsely flood the chips, and owner overrides can be cleared with `report_role: null`.
3. Add automated tests in `backend/tests/test_item_roles.py` and `backend/tests/test_symptom_report.py` covering both behaviors.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, pytest, SvelteKit.

**Spec:** User reports:
1. `Error: 422 ... Input should be 'lifestyle_impact' or 'headache_report' ... input: acupuncture_report`
2. `Deleting selected items doesn't work either. Eg deleting for example - Woke up tired - describes the night..... Will not delete`

## Global Constraints
- Follow `safe-change` skill: develop on a dedicated git branch (`fix/acupuncture-report-settings`), run tests against throwaway Postgres, push to working branch, open PR.
- No database migration required: `activities.hidden_pages` is already a JSON column.
- No `.env` changes required on NUC host.

## Review Focus
- Hiding on `acupuncture_report` via `PUT /activities/{id}/report-settings` succeeds with HTTP 200.
- Unhiding on `acupuncture_report` (removing from list) resets `hidden_pages` to `None` when empty.
- Category-default morning feedback ("Woke up tired" in "Morning / Waking Feedback") is NOT placed in `left_out` when `report_role` is None.
- When an owner explicitly sets an item to `describes_night`, it appears in `left_out`, and clearing `report_role` to `None` (clicking ×) removes it from `left_out`.
- Invalid page names in `hidden_pages` continue to be rejected with HTTP 422.

---

### Task 1: Add Failing Tests for `acupuncture_report` in `hidden_pages`

**Files:**
- Modify: `backend/tests/test_item_roles.py`

**Interfaces:**
- Consumes: `PUT /activities/{id}/report-settings` with `{"hidden_pages": ["acupuncture_report"]}`
- Produces: Failing test assertion confirming 422 occurs before schema fix

- [ ] **Step 1: Write the failing test**

Add `test_hide_on_acupuncture_page_via_api` to `backend/tests/test_item_roles.py`:
```python
def test_hide_on_acupuncture_page_via_api(signed_in, clean_db):
    act = _make_activity(signed_in)
    url = f"/activities/{act['id']}/report-settings"

    body = signed_in.put(url, json={"hidden_pages": ["acupuncture_report"]}).json()
    assert body["hidden_pages"] == ["acupuncture_report"]

    # Test multi-page hiding
    body = signed_in.put(url, json={"hidden_pages": ["lifestyle_impact", "acupuncture_report"]}).json()
    assert body["hidden_pages"] == ["acupuncture_report", "lifestyle_impact"]

    # Test unhiding
    body = signed_in.put(url, json={"hidden_pages": []}).json()
    assert body["hidden_pages"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_item_roles.py::test_hide_on_acupuncture_page_via_api -v`
Expected: FAIL with HTTP 422 `Input should be 'lifestyle_impact' or 'headache_report'`.

---

### Task 2: Update `ActivityReportSettings` Schema in Backend

**Files:**
- Modify: `backend/app/schemas.py:121`

**Interfaces:**
- Consumes: `Literal["lifestyle_impact", "acupuncture_report", "headache_report"]`
- Produces: Updated `ActivityReportSettings` schema accepting `acupuncture_report`

- [ ] **Step 1: Update `hidden_pages` definition in `backend/app/schemas.py`**

```python
class ActivityReportSettings(BaseModel):
    report_role: Optional[Literal["possible_cause", "describes_night", "symptom", "reaction", "habit"]] = None
    hidden_pages: Optional[List[Literal["lifestyle_impact", "acupuncture_report", "headache_report"]]] = Field(default=None, max_length=5)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_item_roles.py::test_hide_on_acupuncture_page_via_api -v`
Expected: PASS

---

### Task 3: Fix `describes_night` Left Out & Deletion Behavior in `symptom_report.py`

**Files:**
- Modify: `backend/app/services/symptom_report.py:145-177`
- Test: `backend/tests/test_symptom_report.py`

**Interfaces:**
- Consumes: `models.Activity`, `effective_role`, `role_was_set_by_owner`
- Produces: `left_out` list in `compute_headache_summary` containing only items explicitly hidden or role-overridden by owner

- [ ] **Step 1: Write the failing test for `describes_night` left-out behavior**

In `backend/tests/test_symptom_report.py`, add `test_category_default_describes_night_not_in_left_out`:
```python
def test_category_default_describes_night_not_in_left_out(clean_db, db):
    cat_morning = _get_or_create_category(db, "Morning / Waking Feedback")
    cat_gen = _get_or_create_category(db, "Misc")

    # Item with default category role (describes_night) but no owner override
    woke_tired = models.Activity(name="Woke up tired", category_id=cat_morning.id, report_role=None)
    # Item with explicit owner role
    explicit_desc = models.Activity(name="Restless", category_id=cat_gen.id, report_role="describes_night")
    db.add_all([woke_tired, explicit_desc])
    db.commit()

    res = compute_headache_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 10))
    left_out = {item["activity"]: item["reason"] for item in res["left_out"]}

    # Default category item should NOT be in left_out
    assert "Woke up tired" not in left_out
    # Explicit owner override item SHOULD be in left_out
    assert left_out.get("Restless") == "describes_night"

    # When owner clears report_role on explicit item, it disappears from left_out
    explicit_desc.report_role = None
    db.commit()
    res2 = compute_headache_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 10))
    left_out2 = {item["activity"]: item["reason"] for item in res2["left_out"]}
    assert "Restless" not in left_out2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_symptom_report.py::test_category_default_describes_night_not_in_left_out -v`
Expected: FAIL (because "Woke up tired" is currently added to `left_out`).

- [ ] **Step 3: Update `backend/app/services/symptom_report.py`**

1. In `explicit_left_out` query (lines 145-159), include `describes_night` when `report_role` is set:
```python
    explicit_left_out = (
        db.query(models.Activity)
        .filter(
            models.Activity.deprecated_at.is_(None),
            (models.Activity.report_role.in_(["habit", "describes_night"])) | (models.Activity.hidden_pages.isnot(None)),
        )
        .all()
    )
    for act in explicit_left_out:
        name = (act.name or "").strip()
        if is_hidden_on(act, ACUPUNCTURE_PAGE):
            left_out_dict[act.id] = {"activity_id": act.id, "activity": name, "reason": "hidden"}
        elif act.report_role in ("habit", "describes_night"):
            left_out_dict[act.id] = {"activity_id": act.id, "activity": name, "reason": act.report_role}
```

2. In the `groups` iteration (lines 173-175), check `role_was_set_by_owner(primary)`:
```python
        if role == "describes_night":
            if role_was_set_by_owner(primary):
                left_out_dict[primary.id] = {"activity_id": primary.id, "activity": name, "reason": "describes_night"}
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_symptom_report.py::test_category_default_describes_night_not_in_left_out -v`
Expected: PASS.

---

### Task 4: Verification, Lint & Commit

**Files:**
- All modified files: `backend/app/schemas.py`, `backend/app/services/symptom_report.py`, `backend/tests/test_item_roles.py`, `backend/tests/test_symptom_report.py`.

- [ ] **Step 1: Run full test suite and linters**

```bash
ruff check backend
ruff format --check backend
TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests -v
```
Expected: All tests pass, 0 lint errors, formatting clean.

- [ ] **Step 2: Commit on working branch**

```bash
git checkout -b fix/acupuncture-report-settings
git add backend/app/schemas.py backend/app/services/symptom_report.py backend/tests/test_item_roles.py backend/tests/test_symptom_report.py
git commit -m "fix(reports): allow acupuncture_report in schema and fix left-out item deletion"
```
