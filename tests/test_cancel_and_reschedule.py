import time_machine


def _book(client, start_time="2026-08-22T09:00:00", email="jane@example.com"):
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": 1,
            "patient_name": "Jane Doe",
            "patient_email": email,
            "patient_phone": "+254700000000",
            "start_time": start_time,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_cancel_appointment_frees_the_slot(client):
    appt = _book(client)

    cancel_resp = client.patch(f"/appointments/{appt['id']}/cancel", json={"reason": "Patient request"})
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"
    assert cancel_resp.json()["cancellation_reason"] == "Patient request"

    availability = client.get("/doctors/1/availability", params={"date": "2026-08-22"})
    starts = [s["start_time"] for s in availability.json()]
    assert "2026-08-22T09:00:00" in starts


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_cancelling_twice_returns_400(client):
    appt = _book(client)
    client.patch(f"/appointments/{appt['id']}/cancel", json={"reason": "Patient request"})

    second = client.patch(f"/appointments/{appt['id']}/cancel", json={"reason": "Again"})
    assert second.status_code == 400
    assert "already cancelled" in second.json()["detail"].lower()


def test_cancel_unknown_appointment_returns_404(client):
    resp = client.patch("/appointments/999/cancel", json={"reason": "n/a"})
    assert resp.status_code == 404


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_reschedule_moves_appointment_and_frees_old_slot(client):
    appt = _book(client, start_time="2026-08-22T09:00:00")

    resp = client.patch(f"/appointments/{appt['id']}/reschedule", json={"start_time": "2026-08-22T10:00:00"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["start_time"] == "2026-08-22T10:00:00"
    assert body["end_time"] == "2026-08-22T10:30:00"

    availability = client.get("/doctors/1/availability", params={"date": "2026-08-22"})
    starts = [s["start_time"] for s in availability.json()]
    assert "2026-08-22T09:00:00" in starts  # old slot freed
    assert "2026-08-22T10:00:00" not in starts  # new slot taken


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_reschedule_into_taken_slot_returns_409(client):
    appt_a = _book(client, start_time="2026-08-22T09:00:00", email="a@example.com")
    _book(client, start_time="2026-08-22T10:00:00", email="b@example.com")

    resp = client.patch(f"/appointments/{appt_a['id']}/reschedule", json={"start_time": "2026-08-22T10:00:00"})
    assert resp.status_code == 409


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_reschedule_cancelled_appointment_returns_400(client):
    appt = _book(client)
    client.patch(f"/appointments/{appt['id']}/cancel", json={"reason": "Patient request"})

    resp = client.patch(f"/appointments/{appt['id']}/reschedule", json={"start_time": "2026-08-22T11:00:00"})
    assert resp.status_code == 400
    assert "cancelled" in resp.json()["detail"].lower()
