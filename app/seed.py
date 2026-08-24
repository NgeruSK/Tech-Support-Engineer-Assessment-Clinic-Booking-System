from datetime import time

from sqlalchemy.orm import Session

from . import models

# Fixed roster: "a small clinic with 5 doctors". Doctors aren't created via
# the API in this version — see README for why.
DOCTORS = [
    {
        "name": "Dr. Amina Yusuf",
        "specialty": "General Practice",
        "phone_number": "+254701234501",
        "work_start": time(9, 0),
        "work_end": time(17, 0),
    },
    {
        "name": "Dr. Brian Otieno",
        "specialty": "Pediatrics",
        "phone_number": "+254701234502",
        "work_start": time(8, 0),
        "work_end": time(16, 0),
    },
    {
        "name": "Dr. Carol Mwangi",
        "specialty": "Dermatology",
        "phone_number": "+254701234503",
        "work_start": time(10, 0),
        "work_end": time(18, 0),
    },
    {
        "name": "Dr. David Kimani",
        "specialty": "Cardiology",
        "phone_number": "+254701234504",
        "work_start": time(9, 0),
        "work_end": time(15, 0),
    },
    {
        "name": "Dr. Esther Njoroge",
        "specialty": "General Practice",
        "phone_number": "+254701234505",
        "work_start": time(9, 0),
        "work_end": time(17, 0),
    },
]


def seed_doctors(db: Session) -> None:
    if db.query(models.Doctor).count() > 0:
        return
    for doctor in DOCTORS:
        db.add(models.Doctor(**doctor))
    db.commit()
