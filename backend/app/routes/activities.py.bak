from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from .. import models, schemas
from .mood import get_db

router = APIRouter()

@router.get("", include_in_schema=False)
@router.get("/", response_model=List[schemas.ActivityResponse])
def list_activities(db: Session = Depends(get_db)):
    return db.query(models.Activity).all()

@router.get("/{activity_id}", response_model=schemas.ActivityResponse)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity

@router.post("", include_in_schema=False)
@router.post("/", response_model=schemas.ActivityResponse)
def create_activity(payload: schemas.ActivityCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Activity).filter(
        models.Activity.name == payload.name,
        models.Activity.category_id == payload.category_id
    ).first()
    if existing:
        return existing

    cat = db.query(models.Category).filter(models.Category.id == payload.category_id).first()
    if not cat:
        raise HTTPException(status_code=400, detail="category_id does not exist")

    new_act = models.Activity(name=payload.name, category_id=payload.category_id)
    db.add(new_act)
    try:
        db.commit()
        db.refresh(new_act)
        return JSONResponse(status_code=201, content=jsonable_encoder(new_act))
    except IntegrityError:
        db.rollback()
        existing = db.query(models.Activity).filter(
            models.Activity.name == payload.name,
            models.Activity.category_id == payload.category_id
        ).first()
        if existing:
            return existing
        raise HTTPException(status_code=500, detail="Could not create activity")

@router.put("/{activity_id}", response_model=schemas.ActivityResponse)
def update_activity(activity_id: int, payload: schemas.ActivityCreate, db: Session = Depends(get_db)):
    act = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    cat = db.query(models.Category).filter(models.Category.id == payload.category_id).first()
    if not cat:
        raise HTTPException(status_code=400, detail="category_id does not exist")
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
