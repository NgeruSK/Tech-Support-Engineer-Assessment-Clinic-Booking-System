import time_machine


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_create_appointment_success(client):
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": 1,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T09:00:00",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "booked"
    assert body["start_time"] == "2026-08-22T09:00:00"
    assert body["end_time"] == "2026-08-22T09:30:00"


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_double_booking_same_slot_returns_409(client):
    payload = {
        "doctor_id": 1,
        "patient_name": "Jane Doe",
        "patient_email": "jane@example.com",
        "patient_phone": "+254700000000",
        "start_time": "2026-08-22T09:00:00",
    }
    first = client.post("/appointments", json=payload)
    assert first.status_code == 201

    second = client.post(
        "/appointments",
        json={**payload, "patient_name": "John Roe", "patient_email": "john@example.com"},
    )
    assert second.status_code == 409
    assert "already booked" in second.json()["detail"].lower()


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_booking_outside_working_hours_returns_400(client):
    # Doctor 1 works 09:00-17:00; 08:00 is before opening.
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": 1,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T08:00:00",
        },
    )
    assert resp.status_code == 400


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_booking_not_aligned_to_slot_grid_returns_400(client, extra_doctor):
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": extra_doctor.id,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T10:17:00",
        },
    )
    assert resp.status_code == 400


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_booking_in_the_past_returns_400(client, extra_doctor):
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": extra_doctor.id,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-21T10:00:00",
        },
    )
    assert resp.status_code == 400
    assert "past" in resp.json()["detail"].lower()


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_booking_within_one_hour_returns_400(client, extra_doctor):
    # 30 minutes from "now" — in the future, but inside the 1-hour buffer.
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": extra_doctor.id,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T07:30:00",
        },
    )
    assert resp.status_code == 400
    assert "1 hour" in resp.json()["detail"].lower()


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_booking_unknown_doctor_returns_404(client):
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": 999,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T09:00:00",
        },
    )
    assert resp.status_code == 404
