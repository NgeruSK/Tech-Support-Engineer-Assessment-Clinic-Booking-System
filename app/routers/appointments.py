from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import booking

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=schemas.AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    return booking.create_appointment(
        db,
        doctor_id=payload.doctor_id,
        patient_name=payload.patient_name,
        patient_email=payload.patient_email,
        patient_phone=payload.patient_phone,
        start_time=payload.start_time,
    )


@router.patch("/{appointment_id}/cancel", response_model=schemas.AppointmentOut)
def cancel_appointment(appointment_id: int, payload: schemas.CancelRequest, db: Session = Depends(get_db)):
    return booking.cancel_appointment(db, appointment_id, payload.reason)


@router.patch("/{appointment_id}/reschedule", response_model=schemas.AppointmentOut)
def reschedule_appointment(appointment_id: int, payload: schemas.RescheduleRequest, db: Session = Depends(get_db)):
    return booking.reschedule_appointment(db, appointment_id, payload.start_time)
