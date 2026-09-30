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
    
    symptom_acts = db.query(models.Activity).filter(
        models.Activity.name.ilike("%headache%") | models.Activity.name.ilike("%migraine%")
    ).all()
    symptom_ids = {a.id for a in symptom_acts}
    
    total_days = len(set(m.timestamp.date() for m in moods)) if moods else 0
    if start_date and end_date and not moods:
        pass
        
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
                    if a.name:
                        day_activities.add(a.name)
                        
        if has_symptom:
            symptom_days.add(date)
            for act_name in day_activities:
                activities_on_symptom_days[act_name] += 1
        else:
            for act_name in day_activities:
                activities_on_clean_days[act_name] += 1

    num_symptom_days = len(symptom_days)
    
    # Calculate total clean days. If we have a strict start and end date, we use that for total days.
    # Otherwise, total days is just the number of unique days logged.
    if start_date and end_date:
        total_days = (end_date - start_date).days + 1
    else:
        total_days = len(moods_by_day)
        
    num_clean_days = total_days - num_symptom_days if total_days > num_symptom_days else 0
    
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
    
    return {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "total_days": total_days,
        "symptom_days": num_symptom_days,
        "average_severity": round(avg_severity, 2) if avg_severity else None,
        "triggers": triggers[:5]
    }
