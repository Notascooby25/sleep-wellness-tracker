from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=List[schemas.CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()

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
