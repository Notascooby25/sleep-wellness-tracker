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
    
    db: Session = Depends(get_db)
):
    
    
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
    
    # Include jaw pain along with headache and migraine
    symptom_acts = db.query(models.Activity).filter(
        models.Activity.name.ilike("%headache%") | 
        models.Activity.name.ilike("%migraine%") |
        models.Activity.name.ilike("%jaw%")
    ).all()
    symptom_ids = {a.id for a in symptom_acts}
    
    symptom_days = set()
    symptom_severities = []
    
    moods_by_day = defaultdict(list)
    day_activities_map = defaultdict(set)
    
    for m in moods:
        d = m.timestamp.date()
        moods_by_day[d].append(m)
        
    for date, day_moods in moods_by_day.items():
        has_symptom = False
        for m in day_moods:
            for a in m.activities:
                if a.id in symptom_ids:
                    has_symptom = True
                    for det in m.activity_details:
                        if det.activity_id == a.id and det.severity is not None:
                            symptom_severities.append(det.severity)
                else:
                    if a.name and not a.ignore_in_reports:
                        day_activities_map[date].add(a.name)
                        
        if has_symptom:
            symptom_days.add(date)

    num_symptom_days = len(symptom_days)
    
    if start_date and end_date:
        total_days = (end_date - start_date).days + 1
    else:
        total_days = len(moods_by_day)
        
    num_clean_days = total_days - num_symptom_days if total_days > num_symptom_days else 0
    clean_days = set(moods_by_day.keys()) - symptom_days

    # Calculate Activity Triggers (Same Day and Day Before)
    activities_on_symptom_days = defaultdict(int)
    activities_on_clean_days = defaultdict(int)
    
    for date in symptom_days:
        # Same day
        for act in day_activities_map.get(date, set()):
            activities_on_symptom_days[f"{act}"] += 1
        # Day before
        prev_date = date - dt.timedelta(days=1)
        for act in day_activities_map.get(prev_date, set()):
            activities_on_symptom_days[f"[Day Before] {act}"] += 1
            
    for date in clean_days:
        # Same day
        for act in day_activities_map.get(date, set()):
            activities_on_clean_days[f"{act}"] += 1
        # Day before
        prev_date = date - dt.timedelta(days=1)
        for act in day_activities_map.get(prev_date, set()):
            activities_on_clean_days[f"[Day Before] {act}"] += 1

    triggers = []
    # Only consider triggers that happen at least twice OR at least on 50% of symptom days
    min_occurrences = max(2, int(num_symptom_days * 0.3))
    
    for act_name, symptom_count in activities_on_symptom_days.items():
        if symptom_count < min_occurrences:
            continue
            
        clean_count = activities_on_clean_days.get(act_name, 0)
        
        symptom_freq = symptom_count / num_symptom_days if num_symptom_days > 0 else 0
        clean_freq = clean_count / num_clean_days if num_clean_days > 0 else 0
        
        # Must be at least 20% more frequent on symptom days
        if symptom_freq > clean_freq + 0.20:
            triggers.append({
                "activity": act_name,
                "symptom_freq": round(symptom_freq * 100),
                "clean_freq": round(clean_freq * 100),
                "difference": round((symptom_freq - clean_freq) * 100)
            })
            
    triggers.sort(key=lambda x: x["difference"], reverse=True)
    
    avg_severity = sum(symptom_severities) / len(symptom_severities) if symptom_severities else None
    
    # Biometrics Analysis (Same Day and Day Before)
    biometric_factors = []
    
    def analyze_metric(model_class, date_col, val_col, name, reverse=False):
        q = db.query(date_col, val_col).filter(val_col.isnot(None))
        # Fetch a slightly wider window to allow for day-before lookups
        if start_date:
            q = q.filter(date_col >= start_date - dt.timedelta(days=1))
        if end_date:
            q = q.filter(date_col <= end_date)
        
        rows = q.all()
        if not rows:
            return
            
        metric_map = {r_date: float(r_val) for r_date, r_val in rows}
        
        # Analyze Same Day
        symp_same = [metric_map[d] for d in symptom_days if d in metric_map]
        clean_same = [metric_map[d] for d in clean_days if d in metric_map]
        
        # Analyze Day Before
        symp_prev = [metric_map[d - dt.timedelta(days=1)] for d in symptom_days if (d - dt.timedelta(days=1)) in metric_map]
        clean_prev = [metric_map[d - dt.timedelta(days=1)] for d in clean_days if (d - dt.timedelta(days=1)) in metric_map]
        
        def evaluate(symp_vals, clean_vals, label):
            if len(symp_vals) > 0 and len(clean_vals) > 0:
                avg_symp = sum(symp_vals) / len(symp_vals)
                avg_clean = sum(clean_vals) / len(clean_vals)
                diff = avg_symp - avg_clean
                
                is_significant = False
                if "Sleep Score" in label and diff < -4:
                    is_significant = True
                elif "Stress" in label and diff > 3:
                    is_significant = True
                elif "Resting Heart Rate" in label and diff > 2:
                    is_significant = True
                    
                if is_significant or abs(diff) > (avg_clean * 0.10 if avg_clean else 1):
                    biometric_factors.append({
                        "metric": label,
                        "symptom_avg": round(avg_symp, 1),
                        "clean_avg": round(avg_clean, 1),
                        "difference": round(diff, 1)
                    })

        evaluate(symp_same, clean_same, f"{name}")
        evaluate(symp_prev, clean_prev, f"[Day Before] {name}")

    analyze_metric(models.GarminSleepDaily, models.GarminSleepDaily.sleep_date, models.GarminSleepDaily.sleep_score, "Sleep Score")
    analyze_metric(models.GarminStressDaily, models.GarminStressDaily.stress_date, models.GarminStressDaily.overall_stress_level, "Stress Level")
    analyze_metric(models.GarminRestingHeartRateDaily, models.GarminRestingHeartRateDaily.heart_rate_date, models.GarminRestingHeartRateDaily.resting_heart_rate, "Resting Heart Rate")

    # Sort biometrics so "Day Before" isn't randomly mixed
    biometric_factors.sort(key=lambda x: (not x["metric"].startswith("[Day Before]"), abs(x["difference"])), reverse=True)

    return {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "total_days": total_days,
        "symptom_days": num_symptom_days,
        "average_severity": round(avg_severity, 2) if avg_severity else None,
        "triggers": triggers[:8],
        "biometrics": biometric_factors
    }
