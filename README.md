# Clinic Booking API

A small clinic with 5 doctors and 30-minute appointment slots. Patients can look up a doctor's free slots for a given day, book one, and later cancel or reschedule it. That's the scope of the system.

**Repository:** https://github.com/NgeruSK/Tech-Support-Engineer-Assessment-Clinic-Booking-System  
**Live API:** https://tech-support-engineer-assessment-clinic.onrender.com/  
**Swagger Docs:** https://tech-support-engineer-assessment-clinic.onrender.com/docs

---

## Section 1 — System design

Three models cover it: **Doctor** (`name`, `specialty`, `phone_number`, `work_start`, `work_end`), **Patient** (`name`, `email`, `phone_number`), and **Appointment** (`doctor_id`, `patient_id`, `start_time`, `end_time`, `status`, `cancellation_reason`).

Phone numbers are stored as plain strings without format validation. The doctors are a fixed roster of 5, seeded on startup rather than created through the API. The brief describes an existing clinic with 5 doctors and doesn't require doctor management, so I kept that part simple.

Patients aren't created through a separate signup step. `POST /appointments` takes the patient's name, email and phone number and gets-or-creates the patient behind the scenes. Email identifies an existing patient, while name and phone are updated if they change.

There is no authentication, since it isn't part of the assessment scope.

I didn't add a separate `Slot` table. Availability is calculated when requested by walking from `work_start` to `work_end` in 30-minute steps and removing slots that already have an active appointment. For a small clinic, this is simpler than maintaining a separate set of slot records.

Working hours are one window per doctor and apply every day of the week. A real clinic would likely need different hours by weekday, holidays and doctor leave. That could be added later with a `DoctorSchedule` model without changing the core booking logic.

One limitation worth noting is concurrent booking. The service checks for an existing appointment at write time rather than relying on a database constraint. This is sufficient for the current single-process SQLite deployment, but it is not fully race-proof under multiple workers. A production version would add database-level protection, such as a unique constraint/index for the doctor and appointment start time.

Cancelled appointments are not deleted. Their status changes to `cancelled` and the cancellation reason is stored. This keeps the history while making the slot available again.

Times are stored as naive UTC datetimes. This keeps things simple for the single-location scenario, but timezone-aware datetimes would be more appropriate for a multi-location system.

SQLite is used by default because it requires no setup. The application uses SQLAlchemy and does not depend on SQLite-specific booking logic, so moving to PostgreSQL later is straightforward.

The code is split so the booking rules don't depend directly on FastAPI:

```text
app/
  main.py                  FastAPI app, startup seeding and HTTP error handling
  database.py              SQLAlchemy engine/session
  models.py                ORM models
  schemas.py               Pydantic request/response models
  seed.py                  the 5 doctors
  services/booking.py      booking rules, validation, cancel/reschedule
  routers/                 API routes

tests/                     pytest tests
```

`services/booking.py` raises its own exceptions (`NotFoundError`, `ValidationError`, `ConflictError`, `AlreadyCancelledError`) rather than FastAPI-specific exceptions. `main.py` maps these to the appropriate HTTP responses, keeping the business logic separate from the API layer.

### Assumptions

- Exactly 5 doctors, fixed and seeded at startup.
- One working-hours window per doctor, applied every day.
- Slots are always 30 minutes.
- Datetimes are treated as naive UTC.
- No authentication is implemented.
- Patients are identified by email when booking.
- Phone numbers are stored without format validation.
- No SMS or email notifications are sent.
- The server's UTC clock is authoritative for "now".
- The 1-hour lead-time restriction is calculated using server UTC time.
- SQLite is the default database.
- The current deployment assumes a single application process.

---

## Section 2 — API implementation

| Method | Path | What it does |
|---|---|---|
| `GET` | `/doctors` | List doctors — name, specialty, phone number and working hours |
| `GET` | `/doctors/{id}/availability?date=YYYY-MM-DD` | Free 30-minute slots for a doctor |
| `POST` | `/appointments` | Book an appointment |
| `PATCH` | `/appointments/{id}/cancel` | Cancel with a reason |
| `PATCH` | `/appointments/{id}/reschedule` | Move an appointment to a new slot |
| `GET` | `/patients/{id}/appointments` | Bonus — upcoming appointments sorted by date |
| `GET` | `/` | Basic landing route |
| `GET` | `/health` | Liveness check |

`GET /doctors` is an additional endpoint that makes the fixed doctor roster available to clients before they request availability.

`/docs` provides FastAPI's automatically generated Swagger documentation.

Booking validates that the doctor exists, the requested time is within working hours, starts on a 30-minute boundary, is not in the past, is at least 1 hour away, and is not already booked.

Cancellation changes the appointment status to `cancelled` and stores the reason. The slot then becomes available again. A second cancellation returns an error.

Rescheduling validates the new slot in the same way as a fresh booking. A cancelled appointment cannot be rescheduled.

Errors use meaningful HTTP status codes:

- `400` for booking/validation rules
- `404` when a doctor, patient or appointment does not exist
- `409` when the requested slot is already booked

Example calls:

```bash
curl "http://localhost:8000/doctors"

curl "http://localhost:8000/doctors/1/availability?date=2026-08-25"

curl -X POST "http://localhost:8000/appointments" \
  -H "Content-Type: application/json" \
  -d '{"doctor_id":1,"patient_name":"Jane Doe","patient_email":"jane@example.com","patient_phone":"+254712345678","start_time":"2026-08-25T09:00:00"}'

curl -X PATCH "http://localhost:8000/appointments/1/cancel" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Feeling better"}'

curl -X PATCH "http://localhost:8000/appointments/1/reschedule" \
  -H "Content-Type: application/json" \
  -d '{"start_time":"2026-08-25T10:00:00"}'

curl "http://localhost:8000/patients/1/appointments"
```

---

## Running it locally

Requires Python 3.11+ (built and tested on Python 3.13). No external database, API keys or `.env` file are required.

```bash
python3 -m venv .venv

source .venv/bin/activate
# Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt

uvicorn app.main:app --reload
```

The server runs at `http://localhost:8000`.

Swagger is available at `http://localhost:8000/docs`.

`DATABASE_URL` defaults to:

```text
sqlite:///./clinic.db
```

The 5 doctors are seeded on startup. Delete `clinic.db` to start with a clean database.

If tests are not needed, `requirements.txt` is enough:

```bash
pip install -r requirements.txt
```

Docker:

```bash
docker build -t clinic-booking-api .

docker run -p 8000:8000 clinic-booking-api
```

---

## Testing

```bash
pip install -r requirements-dev.txt

pytest -v
```

Tests use an in-memory SQLite database.

Time-sensitive rules, including the past-booking check and 1-hour lead-time restriction, are tested with `time-machine` so the current time can be controlled explicitly rather than depending on the actual system clock.

Coverage includes successful bookings, double booking, working-hours validation, 30-minute slot validation, past bookings, the 1-hour restriction, cancellation, double cancellation, rescheduling, occupied reschedule slots, cancelled appointments, availability after booking/cancellation, and upcoming patient appointments.

---

## Section 3 — Deployment & CI/CD

The application is deployed on [Render](https://render.com/) as a Docker web service.

**Live URL:** https://tech-support-engineer-assessment-clinic.onrender.com/

The service is connected to the GitHub repository:

https://github.com/NgeruSK/Tech-Support-Engineer-Assessment-Clinic-Booking-System

`render.yaml` describes the Render service and the `Dockerfile` builds the application.

`main` is the deployment branch.

GitHub Actions runs the test suite on every pull request into `main` and on pushes to `main`.

Once changes are merged into `main`, Render's Git integration automatically detects the change and deploys the latest version.

The flow is:

```text
Pull Request → Tests → Merge to main → Render deployment
```

The GitHub Actions workflow also contains a Render deploy-hook step. With Render's native Git deployment enabled, this is redundant for the current setup, but it provides a fallback if the deployment approach is changed later.

---

## Section 4 — AI Reflection

### 1. What did you use AI for across the four sections?

- **Section 1:** Reviewing system design, data models, assumptions and trade-offs.
- **Section 2:** Assisting with API structure, validation rules, edge cases and tests.
- **Section 3:** Reviewing Docker and GitHub Actions CI/CD configuration.
- **Overall:** Reviewing code, identifying possible issues and suggesting improvements.

AI was used as a development and review tool, while the application and tests were run and verified independently.

### 2. One example where AI improved my work

I used AI to help identify a reliable way to test the time-based booking rules, particularly the **1-hour booking restriction**.

An initial approach relied too much on the actual system time. Using AI to explore alternatives led me to `time-machine`, which allows the tests to explicitly control the current time.

This made the tests deterministic instead of depending on when the test suite happened to run.

### 3. One example where AI was wrong or incomplete

The initial approach to testing time-dependent functionality was not reliable enough because it depended on the actual system clock.

I caught this while reviewing and running the tests. I changed the approach to explicitly control time with `time-machine` and then verified the affected scenarios again.

### 4. Two decisions I made without AI

- **No separate Slot table:** I chose to calculate available slots from working hours and existing appointments because the clinic is small and this avoids unnecessary state to maintain.
- **Keep cancelled appointments:** I chose to mark appointments as cancelled rather than delete them so the cancellation history and reason are retained, while allowing the slot to become available again.

These decisions were based on the assessment scope and my own judgment about keeping the design simple and maintainable.