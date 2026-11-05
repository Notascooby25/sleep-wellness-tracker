from app.database import _ensure_legacy_schema_compatibility


def test_ensure_legacy_schema_compatibility_is_idempotent(clean_db):
    # Running compatibility twice in succession must not raise ProgrammingError or clash
    _ensure_legacy_schema_compatibility()
    _ensure_legacy_schema_compatibility()
