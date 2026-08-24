from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import booking

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/{patient_id}/appointments", response_model=list[schemas.AppointmentOut])
def list_patient_appointments(patient_id: int, db: Session = Depends(get_db)):
    return booking.get_patient_appointments(db, patient_id)
