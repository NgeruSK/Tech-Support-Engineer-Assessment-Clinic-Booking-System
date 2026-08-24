"""Core booking logic, kept independent of FastAPI so it's easy to unit test
and so the HTTP layer (routers/) stays a thin translation of requests/responses.
"""

from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from ..exceptions import AlreadyCancelledError, ConflictError, NotFoundError, ValidationError

SLOT_MINUTES = 30
MIN_LEAD_TIME = timedelta(hours=1)


def _get_doctor(db: Session, doctor_id: int) -> models.Doctor:
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise NotFoundError(f"Doctor {doctor_id} not found")
    return doctor


def _get_patient(db: Session, patient_id: int) -> models.Patient:
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise NotFoundError(f"Patient {patient_id} not found")
    return patient


def _get_appointment(db: Session, appointment_id: int) -> models.Appointment:
    appointment = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if not appointment:
        raise NotFoundError(f"Appointment {appointment_id} not found")
    return appointment


def _slot_starts_for_day(doctor: models.Doctor, on_date: date_type) -> list[datetime]:
    slots = []
    current = datetime.combine(on_date, doctor.work_start)
    end_of_day = datetime.combine(on_date, doctor.work_end)
    while current + timedelta(minutes=SLOT_MINUTES) <= end_of_day:
        slots.append(current)
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def get_available_slots(db: Session, doctor_id: int, on_date: date_type) -> list[dict]:
    doctor = _get_doctor(db, doctor_id)
    all_slots = _slot_starts_for_day(doctor, on_date)

    day_start = datetime.combine(on_date, doctor.work_start)
    day_end = datetime.combine(on_date, doctor.work_end)
    booked_rows = (
        db.query(models.Appointment.start_time)
        .filter(
            models.Appointment.doctor_id == doctor_id,
            models.Appointment.status == models.AppointmentStatus.booked,
            models.Appointment.start_time >= day_start,
            models.Appointment.start_time < day_end,
        )
        .all()
    )
    booked_starts = {row[0] for row in booked_rows}

    now = datetime.utcnow()
    return [
        {"start_time": s, "end_time": s + timedelta(minutes=SLOT_MINUTES)}
        for s in all_slots
        if s not in booked_starts and s >= now + MIN_LEAD_TIME
    ]


def _validate_slot(
    db: Session,
    doctor: models.Doctor,
    start_time: datetime,
    exclude_appointment_id: Optional[int] = None,
) -> datetime:
    """Raises ValidationError / ConflictError if start_time isn't bookable.
    Returns the computed end_time on success.
    """
    end_time = start_time + timedelta(minutes=SLOT_MINUTES)
    now = datetime.utcnow()

    if start_time < now:
        raise ValidationError("Cannot book an appointment in the past")

    if start_time < now + MIN_LEAD_TIME:
        raise ValidationError("Appointments must be made at least 1 hour in advance")

    day_start = datetime.combine(start_time.date(), doctor.work_start)
    day_end = datetime.combine(start_time.date(), doctor.work_end)
    slot_offset_seconds = (start_time - day_start).total_seconds()

    if start_time < day_start or end_time > day_end or slot_offset_seconds % (SLOT_MINUTES * 60) != 0:
        raise ValidationError(
            f"Slot must fall within the doctor's working hours "
            f"({doctor.work_start.strftime('%H:%M')}-{doctor.work_end.strftime('%H:%M')}) "
            f"and align to {SLOT_MINUTES}-minute slots"
        )

    conflict_query = db.query(models.Appointment).filter(
        models.Appointment.doctor_id == doctor.id,
        models.Appointment.status == models.AppointmentStatus.booked,
        models.Appointment.start_time == start_time,
    )
    if exclude_appointment_id is not None:
        conflict_query = conflict_query.filter(models.Appointment.id != exclude_appointment_id)
    if conflict_query.first():
        raise ConflictError("This slot is already booked")

    return end_time


def _get_or_create_patient(db: Session, name: str, email: str, phone_number: str) -> models.Patient:
    patient = db.query(models.Patient).filter(models.Patient.email == email).first()
    if patient:
        # Keep contact details current in case a returning patient's number changed.
        patient.name = name
        patient.phone_number = phone_number
        return patient
    patient = models.Patient(name=name, email=email, phone_number=phone_number)
    db.add(patient)
    db.flush()
    return patient


def create_appointment(
    db: Session,
    doctor_id: int,
    patient_name: str,
    patient_email: str,
    patient_phone: str,
    start_time: datetime,
) -> models.Appointment:
    doctor = _get_doctor(db, doctor_id)
    end_time = _validate_slot(db, doctor, start_time)
    patient = _get_or_create_patient(db, patient_name, patient_email, patient_phone)

    appointment = models.Appointment(
        doctor_id=doctor.id,
        patient_id=patient.id,
        start_time=start_time,
        end_time=end_time,
        status=models.AppointmentStatus.booked,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, appointment_id: int, reason: str) -> models.Appointment:
    appointment = _get_appointment(db, appointment_id)
    if appointment.status == models.AppointmentStatus.cancelled:
        raise AlreadyCancelledError("Appointment is already cancelled")

    appointment.status = models.AppointmentStatus.cancelled
    appointment.cancellation_reason = reason
    db.commit()
    db.refresh(appointment)
    return appointment


def reschedule_appointment(db: Session, appointment_id: int, new_start_time: datetime) -> models.Appointment:
    appointment = _get_appointment(db, appointment_id)
    if appointment.status == models.AppointmentStatus.cancelled:
        raise ValidationError("Cannot reschedule a cancelled appointment")

    doctor = _get_doctor(db, appointment.doctor_id)
    new_end_time = _validate_slot(db, doctor, new_start_time, exclude_appointment_id=appointment.id)

    appointment.start_time = new_start_time
    appointment.end_time = new_end_time
    db.commit()
    db.refresh(appointment)
    return appointment


def get_patient_appointments(db: Session, patient_id: int) -> list[models.Appointment]:
    _get_patient(db, patient_id)
    now = datetime.utcnow()
    return (
        db.query(models.Appointment)
        .filter(
            models.Appointment.patient_id == patient_id,
            models.Appointment.status == models.AppointmentStatus.booked,
            models.Appointment.start_time >= now,
        )
        .order_by(models.Appointment.start_time.asc())
        .all()
    )
