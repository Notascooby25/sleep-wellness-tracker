from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=List[schemas.CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()


@router.get("/position-options/", response_model=List[schemas.PositionOptionResponse])
def list_position_options(db: Session = Depends(get_db)):
    return db.query(models.PositionOption).order_by(models.PositionOption.id.asc()).all()


@router.post("/position-options/", response_model=schemas.PositionOptionResponse)
def create_position_option(payload: schemas.PositionOptionCreate, db: Session = Depends(get_db)):
    label = payload.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="Position label cannot be empty")
    existing = db.query(models.PositionOption).filter(models.PositionOption.label == label).first()
    if existing:
        return existing
    option = models.PositionOption(label=label)
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


@router.put("/position-options/{option_id}", response_model=schemas.PositionOptionResponse)
def update_position_option(option_id: int, payload: schemas.PositionOptionCreate, db: Session = Depends(get_db)):
    option = db.query(models.PositionOption).filter(models.PositionOption.id == option_id).first()
    if not option:
        raise HTTPException(status_code=404, detail="Position option not found")
    label = payload.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="Position label cannot be empty")
    duplicate = (
        db.query(models.PositionOption)
        .filter(models.PositionOption.label == label, models.PositionOption.id != option_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Another position option already uses that label")
    option.label = label
    db.commit()
    db.refresh(option)
    return option


@router.delete("/position-options/{option_id}", status_code=204)
def delete_position_option(option_id: int, db: Session = Depends(get_db)):
    option = db.query(models.PositionOption).filter(models.PositionOption.id == option_id).first()
    if not option:
        raise HTTPException(status_code=404, detail="Position option not found")
    db.delete(option)
    db.commit()
    return


@router.get("/{category_id}", response_model=schemas.CategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.post("/", response_model=schemas.CategoryResponse)
def create_category(payload: schemas.CategoryCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Category).filter(models.Category.name == payload.name).first()
    if existing:
        return existing
    new_cat = models.Category(
        name=payload.name,
        require_rating=payload.require_rating,
        rating_label=payload.rating_label,
        supports_position=payload.supports_position,
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@router.put("/{category_id}", response_model=schemas.CategoryResponse)
def update_category(category_id: int, payload: schemas.CategoryCreate, db: Session = Depends(get_db)):
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.name = payload.name
    cat.require_rating = payload.require_rating
    cat.rating_label = payload.rating_label
    cat.supports_position = payload.supports_position
    db.commit()
    db.refresh(cat)
    return cat

@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    has_acts = db.query(models.Activity).filter(models.Activity.category_id == category_id).first()
    if has_acts:
        raise HTTPException(status_code=400, detail="Category has activities; delete them first")
    db.delete(cat)
    db.commit()
    return
