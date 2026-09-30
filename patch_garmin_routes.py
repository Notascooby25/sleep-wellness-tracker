import re

with open("backend/app/routes/garmin.py", "r") as f:
    content = f.read()

serializers = """
def _serialize_respiration(row: models.GarminRespirationDaily) -> dict:
    return {
        "respiration_date": row.respiration_date.isoformat(),
        "lowest_respiration_value": float(row.lowest_respiration_value) if row.lowest_respiration_value is not None else None,
        "highest_respiration_value": float(row.highest_respiration_value) if row.highest_respiration_value is not None else None,
        "sleep_avg_respiration_value": float(row.sleep_avg_respiration_value) if row.sleep_avg_respiration_value is not None else None,
    }

def _serialize_spo2(row: models.GarminSpO2Daily) -> dict:
    return {
        "spo2_date": row.spo2_date.isoformat(),
        "average_spo2": float(row.average_spo2) if row.average_spo2 is not None else None,
        "lowest_spo2": float(row.lowest_spo2) if row.lowest_spo2 is not None else None,
    }

def _serialize_training_status(row: models.GarminTrainingStatusDaily) -> dict:
    return {
        "status_date": row.status_date.isoformat(),
        "training_status": row.training_status,
        "load_status": row.load_status,
        "vo2_max_precise_value": float(row.vo2_max_precise_value) if row.vo2_max_precise_value is not None else None,
    }
"""

if "def _serialize_respiration" not in content:
    content = content.replace("def _serialize_activity", serializers + "\n\ndef _serialize_activity")

routes = """
@router.get("/respiration/latest")
def get_latest_respiration(db: Session = Depends(get_db)):
    row = db.query(models.GarminRespirationDaily).order_by(models.GarminRespirationDaily.respiration_date.desc()).first()
    return {"data": _serialize_respiration(row) if row else None}

@router.get("/spo2/latest")
def get_latest_spo2(db: Session = Depends(get_db)):
    row = db.query(models.GarminSpO2Daily).order_by(models.GarminSpO2Daily.spo2_date.desc()).first()
    return {"data": _serialize_spo2(row) if row else None}

@router.get("/training-status/latest")
def get_latest_training_status(db: Session = Depends(get_db)):
    row = db.query(models.GarminTrainingStatusDaily).order_by(models.GarminTrainingStatusDaily.status_date.desc()).first()
    return {"data": _serialize_training_status(row) if row else None}
"""

if "@router.get(\"/respiration/latest\")" not in content:
    content += "\n" + routes

with open("backend/app/routes/garmin.py", "w") as f:
    f.write(content)
