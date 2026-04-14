from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/activities", tags=["activities"])

@router.get("/", response_model=List[schemas.ActivityResponse])
def list_activities(db: Session = Depends(get_db)):
    return db.query(models.Activity).all()

@router.get("/{activity_id}", response_model=schemas.ActivityResponse)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    act = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    return act

@router.post("/", response_model=schemas.ActivityResponse)
def create_activity(payload: schemas.ActivityCreate, db: Session = Depends(get_db)):
    new_act = models.Activity(name=payload.name, category_id=payload.category_id)
    db.add(new_act)
    db.commit()
    db.refresh(new_act)
    return new_act

@router.put("/{activity_id}", response_model=schemas.ActivityResponse)
def update_activity(activity_id: int, payload: schemas.ActivityCreate, db: Session = Depends(get_db)):
    act = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    act.name = payload.name
    act.category_id = payload.category_id
    db.commit()
    db.refresh(act)
    return act

@router.delete("/{activity_id}", status_code=204)
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    act = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(act)
    db.commit()
    return
