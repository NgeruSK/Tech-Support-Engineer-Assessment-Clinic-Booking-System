import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import relationship

from .database import Base


class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    cancelled = "cancelled"


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    specialty = Column(String, nullable=True)
    phone_number = Column(String, nullable=False)
    # Same working hours every day, applied uniformly across the week.
    # A real rollout would need per-weekday schedules / time off — see README.
    work_start = Column(Time, nullable=False)
    work_end = Column(Time, nullable=False)

    appointments = relationship("Appointment", back_populates="doctor")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    phone_number = Column(String, nullable=False)

    appointments = relationship("Appointment", back_populates="patient")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.booked, nullable=False)
    cancellation_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    doctor = relationship("Doctor", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
