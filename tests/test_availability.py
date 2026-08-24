import time_machine


def test_list_doctors_includes_phone_number(client):
    resp = client.get("/doctors")
    assert resp.status_code == 200
    doctors = resp.json()
    assert len(doctors) == 5
    assert all(d["phone_number"] for d in doctors)


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_availability_lists_all_slots_when_nothing_booked(client):
    # Doctor 1 (seeded): 09:00-17:00 -> 16 half-hour slots in a day.
    resp = client.get("/doctors/1/availability", params={"date": "2026-08-22"})
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) == 16
    assert slots[0]["start_time"] == "2026-08-22T09:00:00"
    assert slots[-1]["start_time"] == "2026-08-22T16:30:00"


@time_machine.travel("2026-08-22 07:00:00+00:00", tick=False)
def test_booked_slot_is_excluded_from_availability(client):
    client.post(
        "/appointments",
        json={
            "doctor_id": 1,
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": "2026-08-22T09:00:00",
        },
    )

    resp = client.get("/doctors/1/availability", params={"date": "2026-08-22"})
    starts = [s["start_time"] for s in resp.json()]
    assert "2026-08-22T09:00:00" not in starts
    assert "2026-08-22T09:30:00" in starts


def test_availability_for_unknown_doctor_returns_404(client):
    resp = client.get("/doctors/999/availability", params={"date": "2026-08-22"})
    assert resp.status_code == 404
