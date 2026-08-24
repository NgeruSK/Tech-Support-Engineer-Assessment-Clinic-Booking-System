from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialty: Optional[str] = None
    phone_number: str
    work_start: time
    work_end: time


class SlotOut(BaseModel):
    start_time: datetime
    end_time: datetime


class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_name: str = Field(..., min_length=1)
    patient_email: EmailStr
    patient_phone: str = Field(..., min_length=1)
    start_time: datetime


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int
    start_time: datetime
    end_time: datetime
    status: str
    cancellation_reason: Optional[str] = None


class CancelRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class RescheduleRequest(BaseModel):
    start_time: datetime
