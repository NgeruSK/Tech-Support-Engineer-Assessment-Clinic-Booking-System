import os

# Must be set before app.main / app.database are imported anywhere.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from datetime import time

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app import models


@pytest.fixture(autouse=True)
def _clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    # TestClient's context manager fires the startup event, which reseeds
    # the 5 doctors against the freshly emptied tables from _clean_db.
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def extra_doctor(db_session):
    """A doctor with wide-open hours, used only for edge-case tests
    (past bookings / within-lead-time) where working hours would otherwise
    interfere with the thing actually being tested.
    """
    doctor = models.Doctor(
        name="Dr. Edge Case",
        specialty="Testing",
        phone_number="+254700000099",
        work_start=time(0, 0),
        work_end=time(23, 30),
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor
