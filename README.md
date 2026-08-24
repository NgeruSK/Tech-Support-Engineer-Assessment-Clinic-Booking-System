# Clinic Booking API

A small clinic, 5 doctors, 30-minute appointment slots. Patients look up a doctor's
free slots for a given day, book one, and can cancel or reschedule later. That's the
whole scope — this README walks through how it's modeled, how the API behaves, how to
run it, and how it's deployed.

## Section 1 — System design

Three models cover it: **Doctor** (`name`, `specialty`, `phone_number`, `work_start`,
`work_end`), **Patient** (`name`, `email`, `phone_number`), and **Appointment**
(`doctor_id`, `patient_id`, `start_time`, `end_time`, `status`, `cancellation_reason`).
Phone numbers are plain strings, no format validation — good enough for a clinic
that needs a number to call, not something that needs to reject malformed input at
the API boundary. The doctors are a fixed roster of 5, seeded on startup rather than
created through the API — the brief describes a clinic that already has 5 doctors, it
doesn't ask for a way to add more, so I didn't build one. Patients aren't created
through a separate signup step either; `POST /appointments` takes a name, email, and
phone number and gets-or-creates the patient behind the scenes, updating the stored
name/phone if they've changed since the last booking. There's no login. That's fine
for a take-home, but it does mean `GET /patients/{id}/appointments` is reachable by
anyone who knows the ID — a real version of this needs auth in front of it before that
endpoint goes anywhere near production.

I didn't add a "Slot" table. Availability for a doctor on a date is computed each time
it's asked for: walk from `work_start` to `work_end` in 30-minute steps, drop the ones
that already have a booked appointment. Keeping a slots table in sync as doctors'
hours change felt like more moving parts than the problem needed — recomputing a day's
worth of slots is cheap, and there's nothing to expire or regenerate.

Working hours are one window per doctor, applied every day of the week. Real clinics
have different hours on different days and take time off, obviously, but that's a
schema change (a `DoctorSchedule` table keyed by weekday) rather than a rewrite of the
booking logic — the function that generates a day's slots doesn't care where the hours
come from.

One thing I want to be upfront about rather than gloss over: booking conflicts are
caught by re-checking for an existing appointment at write time, not by a database
constraint. That's fine under SQLite with one worker process, which is what this runs
as, but it's not race-proof — two simultaneous requests for the same slot on a real
multi-worker deployment could both slip through. The actual fix is a unique index on
`(doctor_id, start_time)` scoped to booked appointments. I didn't add it because
SQLite doesn't get much value from it and it would need to move with the eventual
Postgres migration anyway, but a reviewer should know the gap is there rather than
assume it's handled.

A few smaller calls: cancelling never deletes the row (status flips to `cancelled`,
reason gets stored) — otherwise there's no way to reject a second cancel with a
sensible error, and you lose the audit trail for free. Times are naive UTC throughout,
no timezone awareness — reasonable for one location, would need revisiting for a
multi-branch clinic. And the DB is SQLite by default purely because it's zero setup;
swapping to Postgres later is a one-line `DATABASE_URL` change since nothing in the
models or the booking logic touches SQLite specifically.

Code is split so the booking rules don't know FastAPI exists:

```
app/
  main.py                  FastAPI app, startup seeding, maps domain errors to HTTP status codes
  database.py              SQLAlchemy engine/session
  models.py                ORM models
  schemas.py               Pydantic request/response bodies
  seed.py                  the 5 doctors
  services/booking.py      the actual rules — slot generation, validation, cancel/reschedule
  routers/                 parses the request, calls the service, returns the result
tests/                     pytest against the booking rules
```

`services/booking.py` takes a DB session and plain values, and raises its own
exceptions (`NotFoundError`, `ValidationError`, `ConflictError`, `AlreadyCancelledError`)
instead of anything FastAPI-specific. `main.py` catches those and turns them into 404 /
400 / 409 responses in one place. Routers end up being a few lines each.

### Assumptions

Most of these are already explained above, in context — this is the same list
gathered in one place so nothing's buried in a paragraph:

- Exactly 5 doctors, fixed at startup. Nothing creates, edits, or removes one — the
  roster in `app/seed.py` is the whole roster.
- One working-hours window per doctor, applied every day of the week. No days off, no
  per-weekday hours, no holidays.
- Slots are always exactly 30 minutes — not configurable per doctor or appointment type.
- All datetimes are naive UTC. `start_time` in a request is taken as UTC as-is; there's
  no timezone field and no conversion. Whatever timezone a client is actually in, it's
  on them to send UTC.
- No authentication anywhere. Any client can book, cancel, reschedule, or read any
  patient's upcoming appointments given the right ID.
- A patient is identified by email, not by an ID a client would already have. Booking
  with an email seen before reuses that patient record and overwrites the stored
  name/phone with whatever was sent this time.
- Phone numbers are unvalidated strings — no format check, no country-code enforcement.
- Nothing is actually sent anywhere. Phone numbers and emails are stored, not acted on
  — no SMS/email confirmation, reminder, or cancellation notice exists. Collecting
  contact info and doing something with it are two different features; only the first
  is built.
- Single-process deployment. The no-double-booking check is a re-check at write time,
  not a database constraint — safe under one worker, not guaranteed under several (see
  the concurrency note above).
- The server's own clock is authoritative for "now." The past-booking check and the
  1-hour lead-time buffer both compare against server UTC time, not anything a client
  claims the current time is.

## Section 2 — API implementation

| Method | Path | What it does |
|---|---|---|
| `GET` | `/doctors` | List doctors — name, specialty, phone number, working hours |
| `GET` | `/doctors/{id}/availability?date=YYYY-MM-DD` | Free 30-min slots for a doctor on a date |
| `POST` | `/appointments` | Book a slot — `doctor_id`, `patient_name`, `patient_email`, `patient_phone`, `start_time` |
| `PATCH` | `/appointments/{id}/cancel` | Cancel with a `reason`; 400 if already cancelled |
| `PATCH` | `/appointments/{id}/reschedule` | Move to a new `start_time`, validated like a fresh booking; 400 if cancelled |
| `GET` | `/patients/{id}/appointments` | Bonus — upcoming appointments, sorted by date |
| `GET` | `/` | Landing route — service name and pointers to `/docs` and `/health` |
| `GET` | `/health` | Liveness check |

`GET /doctors` isn't in the original brief, but it's what makes a doctor's phone
number actually reachable — a patient picking who to book with needs to see the
roster (and be able to call ahead) before hitting the availability endpoint.

`/docs` gets you Swagger, generated automatically, for poking at this by hand.

Errors come back as `{"detail": "..."}` with a status that actually means something:
400 for anything that fails a booking rule (outside working hours, not aligned to the
30-minute grid, in the past, inside the 1-hour lead-time buffer, already
cancelled, rescheduling something cancelled), 404 when the doctor/patient/appointment
doesn't exist, 409 specifically for "someone already has this slot."

A few example calls:

```bash
curl "http://localhost:8000/doctors"

curl "http://localhost:8000/doctors/1/availability?date=2026-08-25"

curl -X POST http://localhost:8000/appointments \
  -H "Content-Type: application/json" \
  -d '{"doctor_id":1,"patient_name":"Jane Doe","patient_email":"jane@example.com","patient_phone":"+254712345678","start_time":"2026-08-25T09:00:00"}'

curl -X PATCH http://localhost:8000/appointments/1/cancel \
  -H "Content-Type: application/json" -d '{"reason":"Feeling better"}'

curl -X PATCH http://localhost:8000/appointments/1/reschedule \
  -H "Content-Type: application/json" -d '{"start_time":"2026-08-25T10:00:00"}'

curl "http://localhost:8000/patients/1/appointments"
```

## Running it locally

Needs Python 3.11+ (built and tested on 3.13). Nothing else — no external database,
no API keys, no `.env` file.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

`DATABASE_URL` defaults to `sqlite:///./clinic.db`, and the 5 doctors seed themselves
into it on first startup — delete `clinic.db` any time you want a clean slate. The
server listens on `http://localhost:8000`; Swagger docs live at
`http://localhost:8000/docs`.

`requirements-dev.txt` pulls in `requirements.txt` plus the test dependencies (pytest,
httpx, time-machine). If you only want to run the server and don't care about running
tests, `pip install -r requirements.txt` on its own is enough.

Docker works the same way, on the same port:

```bash
docker build -t clinic-booking-api .
docker run -p 8000:8000 clinic-booking-api
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest -v
```

Runs against an in-memory SQLite DB (`tests/conftest.py` sets `DATABASE_URL` before
anything else imports). Time-sensitive rules — the past-booking check, the 1-hour
buffer — are tested with [`time-machine`](https://github.com/adamchainz/time-machine)
pinning "now" explicitly in UTC, rather than relying on whatever the clock happens to
say when the suite runs. (Worth reading Section 4 below — that library choice wasn't
the first one I tried, and the reason it changed is a decent story.)

Coverage: the doctor listing, booking success, double-booking, outside working hours,
off the 30-minute grid, in the past, inside the 1-hour window, cancel, double-cancel,
reschedule (including into an already-taken slot, and rescheduling something
cancelled), availability correctly reflecting bookings/cancellations, and the patient-appointments
endpoint.

## Section 3 — Deployment & CI/CD

Deploying to [Render](https://render.com) as a Docker web service — `render.yaml`
describes the service, the `Dockerfile` builds it. Public URL: *to be filled in once
the repo is connected.* Any host that takes a Dockerfile and gives you a webhook to
trigger a redeploy (Railway, Fly.io) would work identically here — nothing in the
pipeline is Render-specific except the one `curl` target.

`main` is the branch that matters. The GitHub Actions workflow (`.github/workflows/ci.yml`)
has two jobs. `test` runs on every PR into `main` and every push to `main` — installs
deps, runs pytest, and that's the actual gate if branch protection is turned on.
`deploy` only runs on a push to `main`, only after `test` passes, and it just hits a
Render deploy hook URL stored as a repo secret (`RENDER_DEPLOY_HOOK_URL`).

To turn deployment on: spin up the Render service from `render.yaml`, grab the deploy
hook URL from its dashboard, add it as that GitHub secret. Without the secret, `test`
still runs and still gates PRs — `deploy` just fails loudly instead of silently doing
nothing, which felt like the safer default.


