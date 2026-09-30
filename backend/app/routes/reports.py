import datetime as dt
from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from .. import models

router = APIRouter()

@router.get("/acupuncture-sessions")
def get_acupuncture_sessions(db: Session = Depends(get_db)):
    activities = db.query(models.Activity).filter(models.Activity.name.ilike("%acupuncture%")).all()
    if not activities:
        return {"sessions": []}
    
    activity_ids = [a.id for a in activities]
    
    moods = (
        db.query(models.Mood)
        .join(models.mood_activities)
        .filter(models.mood_activities.c.activity_id.in_(activity_ids))
        .order_by(models.Mood.timestamp.desc())
        .all()
    )
    
    dates = sorted(list(set([m.timestamp.date() for m in moods])), reverse=True)
    return {"sessions": [d.isoformat() for d in dates]}


@router.get("/headache-summary")
def get_headache_summary(
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    exclude_activities: list[str] = Query([]),
    db: Session = Depends(get_db)
):
    excluded_set = {x.lower().strip() for x in exclude_activities}
    
    query = db.query(models.Mood).options(
        selectinload(models.Mood.activities),
        selectinload(models.Mood.activity_details)
    )
    
    if start_date:
        start_dt = dt.datetime.combine(start_date, dt.time.min).replace(tzinfo=dt.timezone.utc)
        query = query.filter(models.Mood.timestamp >= start_dt)
    if end_date:
        end_dt = dt.datetime.combine(end_date, dt.time.max).replace(tzinfo=dt.timezone.utc)
        query = query.filter(models.Mood.timestamp <= end_dt)
        
    moods = query.order_by(models.Mood.timestamp.asc()).all()
    
    symptom_acts = db.query(models.Activity).filter(
        models.Activity.name.ilike("%headache%") | models.Activity.name.ilike("%migraine%")
    ).all()
    symptom_ids = {a.id for a in symptom_acts}
    
    symptom_days = set()
    symptom_severities = []
    
    activities_on_symptom_days = defaultdict(int)
    activities_on_clean_days = defaultdict(int)
    
    moods_by_day = defaultdict(list)
    for m in moods:
        moods_by_day[m.timestamp.date()].append(m)
        
    for date, day_moods in moods_by_day.items():
        has_symptom = False
        day_activities = set()
        for m in day_moods:
            for a in m.activities:
                if a.id in symptom_ids:
                    has_symptom = True
                    for d in m.activity_details:
                        if d.activity_id == a.id and d.severity is not None:
                            symptom_severities.append(d.severity)
                else:
                    if a.name and a.name.lower().strip() not in excluded_set:
                        day_activities.add(a.name)
                        
        if has_symptom:
            symptom_days.add(date)
            for act_name in day_activities:
                activities_on_symptom_days[act_name] += 1
        else:
            for act_name in day_activities:
                activities_on_clean_days[act_name] += 1

    num_symptom_days = len(symptom_days)
    
    if start_date and end_date:
        total_days = (end_date - start_date).days + 1
    else:
        total_days = len(moods_by_day)
        
    num_clean_days = total_days - num_symptom_days if total_days > num_symptom_days else 0
    clean_days = set(moods_by_day.keys()) - symptom_days

    triggers = []
    for act_name, symptom_count in activities_on_symptom_days.items():
        if symptom_count < 2:
            continue
        clean_count = activities_on_clean_days.get(act_name, 0)
        
        symptom_freq = symptom_count / num_symptom_days if num_symptom_days > 0 else 0
        clean_freq = clean_count / num_clean_days if num_clean_days > 0 else 0
        
        if symptom_freq > clean_freq + 0.15:
            triggers.append({
                "activity": act_name,
                "symptom_freq": round(symptom_freq * 100),
                "clean_freq": round(clean_freq * 100),
                "difference": round((symptom_freq - clean_freq) * 100)
            })
            
    triggers.sort(key=lambda x: x["difference"], reverse=True)
    
    avg_severity = sum(symptom_severities) / len(symptom_severities) if symptom_severities else None
    
    biometric_factors = []
    
    def analyze_metric(model_class, date_col, val_col, name):
        q = db.query(date_col, val_col).filter(val_col.isnot(None))
        if start_date:
            q = q.filter(date_col >= start_date)
        if end_date:
            q = q.filter(date_col <= end_date)
        
        rows = q.all()
        if not rows:
            return
            
        symp_vals = []
        clean_vals = []
        for r_date, r_val in rows:
            if r_date in symptom_days:
                symp_vals.append(float(r_val))
            elif r_date in clean_days or (num_symptom_days > 0 and num_clean_days > 0 and r_date not in symptom_days): 
                clean_vals.append(float(r_val))
                    
        if len(symp_vals) > 0 and len(clean_vals) > 0:
            avg_symp = sum(symp_vals) / len(symp_vals)
            avg_clean = sum(clean_vals) / len(clean_vals)
            diff = avg_symp - avg_clean
            
            is_significant = False
            if name == "Sleep Score" and diff < -4:
                is_significant = True
            elif name == "Stress Level" and diff > 3:
                is_significant = True
            elif name == "Resting Heart Rate" and diff > 2:
                is_significant = True
                
            if is_significant or abs(diff) > (avg_clean * 0.05 if avg_clean else 1):
                biometric_factors.append({
                    "metric": name,
                    "symptom_avg": round(avg_symp, 1),
                    "clean_avg": round(avg_clean, 1),
                    "difference": round(diff, 1)
                })

    analyze_metric(models.GarminSleepDaily, models.GarminSleepDaily.sleep_date, models.GarminSleepDaily.sleep_score, "Sleep Score")
    analyze_metric(models.GarminStressDaily, models.GarminStressDaily.stress_date, models.GarminStressDaily.overall_stress_level, "Stress Level")
    analyze_metric(models.GarminRestingHeartRateDaily, models.GarminRestingHeartRateDaily.heart_rate_date, models.GarminRestingHeartRateDaily.resting_heart_rate, "Resting Heart Rate")

    return {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "total_days": total_days,
        "symptom_days": num_symptom_days,
        "average_severity": round(avg_severity, 2) if avg_severity else None,
        "triggers": triggers[:5],
        "biometrics": biometric_factors
    }
