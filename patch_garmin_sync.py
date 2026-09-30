import re

with open("backend/app/services/garmin_sync.py", "r") as f:
    content = f.read()

upserts = """
def _upsert_respiration_daily(db: Session, target_date: dt.date, payload: Dict[str, Any]) -> models.GarminRespirationDaily:
    row = db.query(models.GarminRespirationDaily).filter(models.GarminRespirationDaily.respiration_date == target_date).first()
    if not row:
        row = models.GarminRespirationDaily(respiration_date=target_date)
        db.add(row)

    row.lowest_respiration_value = _get_value(payload, "lowestRespirationValue", "minRespirationValue")
    row.highest_respiration_value = _get_value(payload, "highestRespirationValue", "maxRespirationValue")
    row.sleep_avg_respiration_value = _get_value(payload, "sleepAvgRespirationValue", "sleepAverageRespirationValue", "averageRespirationValue")
    row.payload = payload
    return row

def _upsert_spo2_daily(db: Session, target_date: dt.date, payload: Dict[str, Any]) -> models.GarminSpO2Daily:
    row = db.query(models.GarminSpO2Daily).filter(models.GarminSpO2Daily.spo2_date == target_date).first()
    if not row:
        row = models.GarminSpO2Daily(spo2_date=target_date)
        db.add(row)

    row.average_spo2 = _get_value(payload, "averageSpO2", "averageSpO2Value", "averageSpO2PR")
    row.lowest_spo2 = _get_value(payload, "lowestSpO2", "lowestSpO2Value", "lowestSpO2PR")
    row.payload = payload
    return row

def _upsert_training_status_daily(db: Session, target_date: dt.date, payload: Dict[str, Any]) -> models.GarminTrainingStatusDaily:
    row = db.query(models.GarminTrainingStatusDaily).filter(models.GarminTrainingStatusDaily.status_date == target_date).first()
    if not row:
        row = models.GarminTrainingStatusDaily(status_date=target_date)
        db.add(row)

    row.training_status = _get_text(payload, "trainingStatus", "status")
    row.load_status = _get_text(payload, "loadStatus", "load")
    row.vo2_max_precise_value = _get_value(payload, "vo2MaxPreciseValue", "vo2Max", "vo2MaxValue")
    row.payload = payload
    return row

def _sync_respiration_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "respiration", _fetch_respiration_payload, _upsert_respiration_daily)

def _sync_spo2_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "spo2", _fetch_spo2_payload, _upsert_spo2_daily)

def _sync_training_status_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "training_status", _fetch_training_status_payload, _upsert_training_status_daily)

def sync_respiration_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _sync_if_due(db, "respiration", force, backfill_days, _sync_respiration_dates)

def sync_spo2_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _sync_if_due(db, "spo2", force, backfill_days, _sync_spo2_dates)

def sync_training_status_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _sync_if_due(db, "training_status", force, backfill_days, _sync_training_status_dates)

"""

if "def _upsert_respiration_daily" not in content:
    content = content.replace("def _sync_sleep_dates", upserts + "\n\ndef _sync_sleep_dates")

# Add to sync_smart
sync_smart_addition = """
    if "respiration" not in results:
        results["respiration"] = sync_respiration_if_due(db, force=force, backfill_days=backfill_days)
    if "spo2" not in results:
        results["spo2"] = sync_spo2_if_due(db, force=force, backfill_days=backfill_days)
    if "training_status" not in results:
        results["training_status"] = sync_training_status_if_due(db, force=force, backfill_days=backfill_days)
"""

if "results[\"respiration\"] =" not in content:
    content = content.replace("return results", sync_smart_addition + "\n    return results")

with open("backend/app/services/garmin_sync.py", "w") as f:
    f.write(content)
