import time_machine


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_patient_appointments_sorted_ascending_and_excludes_cancelled(client):
    later = client.post(
        "/appointments",
        json={
            "doctor_id": 1,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T14:00:00",
        },
    ).json()
    earlier = client.post(
        "/appointments",
        json={
            "doctor_id": 2,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T09:00:00",
        },
    ).json()
    cancelled = client.post(
        "/appointments",
        json={
            "doctor_id": 3,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T12:00:00",
        },
    ).json()
    client.patch(f"/appointments/{cancelled['id']}/cancel", json={"reason": "Changed mind"})

    patient_id = earlier["patient_id"]
    resp = client.get(f"/patients/{patient_id}/appointments")
    assert resp.status_code == 200
    body = resp.json()

    assert [a["id"] for a in body] == [earlier["id"], later["id"]]


def test_appointments_for_unknown_patient_returns_404(client):
    resp = client.get("/patients/999/appointments")
    assert resp.status_code == 404
