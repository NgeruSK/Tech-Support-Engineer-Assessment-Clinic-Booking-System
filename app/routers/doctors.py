from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import booking

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[schemas.DoctorOut])
def list_doctors(db: Session = Depends(get_db)):
    return db.query(models.Doctor).order_by(models.Doctor.id).all()


@router.get("/{doctor_id}/availability", response_model=list[schemas.SlotOut])
def get_availability(
    doctor_id: int,
    date: date_type = Query(..., description="Date to check availability for, e.g. 2026-08-25"),
    db: Session = Depends(get_db),
):
    return booking.get_available_slots(db, doctor_id, date)
