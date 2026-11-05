import pytest
from sqlalchemy import text
from app import models
from app.services import item_roles
from app.database import _ensure_legacy_schema_compatibility


def test_is_symptom_from_explicit_role():
    act = models.Activity(name="Custom Pain", report_role="symptom")
    assert item_roles.is_symptom(act) is True


def test_is_symptom_from_headache_category():
    cat = models.Category(name="Headache Issues")
    act = models.Activity(name="Sharp Tension", category=cat)
    assert item_roles.is_symptom(act) is True


def test_is_symptom_false_for_cause():
    cat = models.Category(name="Food / Drink")
    act = models.Activity(name="Coffee", category=cat)
    assert item_roles.is_symptom(act) is False


def test_startup_migration_sets_symptom_role(db):
    # Setup activities with report_role=None
    cat_symp = db.query(models.Category).filter(models.Category.name == "Headache Issues").first()
    if not cat_symp:
        cat_symp = models.Category(name="Headache Issues")
        db.add(cat_symp)
        db.flush()
    cat_other = db.query(models.Category).filter(models.Category.name == "General").first()
    if not cat_other:
        cat_other = models.Category(name="General")
        db.add(cat_other)
        db.flush()

    a1 = models.Activity(name="Throbbing Headache", report_role=None, category_id=cat_other.id)
    a2 = models.Activity(name="Migraine Aura", report_role=None, category_id=cat_other.id)
    a3 = models.Activity(name="Jaw Tension", report_role=None, category_id=cat_other.id)
    a4 = models.Activity(name="Unrelated Pain", report_role=None, category_id=cat_symp.id)
    a5 = models.Activity(name="Coffee", report_role=None, category_id=cat_other.id)
    db.add_all([a1, a2, a3, a4, a5])
    db.commit()

    # Run migration
    _ensure_legacy_schema_compatibility()

    db.expire_all()
    assert db.get(models.Activity, a1.id).report_role == "symptom"
    assert db.get(models.Activity, a2.id).report_role == "symptom"
    assert db.get(models.Activity, a3.id).report_role == "symptom"
    assert db.get(models.Activity, a4.id).report_role == "symptom"
    assert db.get(models.Activity, a5.id).report_role is None
