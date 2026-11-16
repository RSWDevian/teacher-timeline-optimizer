import os
import time

import pytest
from fastapi.testclient import TestClient

SCENARIO_PAYLOAD = {
    "name": "Term 1",
    "description": "Grade 9 schedule",
    "teachers": [
        {"id": "t1", "name": "Smith", "subject": ["Math"],
         "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
         "max_hours_per_week": 15, "unavailable_slots": ["Mon-1"]},
        {"id": "t2", "name": "Jones", "subject": ["Chemistry"],
         "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
         "max_hours_per_week": 10},
    ],
    "rooms": [
        {"id": "r1", "capacity": 30, "is_lab": False},
        {"id": "r2", "capacity": 32, "is_lab": True},
    ],
    "class_groups": [{"id": "g1", "name": "Grade 9-A", "size": 25}],
    "courses": [
        {"id": "c1", "subject": "Math", "required_hours": 3, "requires_lab": False,
         "allowed_teachers": ["t1"], "class_group_id": "g1", "max_per_day": 2},
        {"id": "c2", "subject": "Chemistry", "required_hours": 2, "requires_lab": True,
         "allowed_teachers": ["t2"], "class_group_id": "g1"},
    ],
    "preferences": {"gap_weight": 8.0, "spread_weight": 2.0, "balance_weight": 1.0},
}


@pytest.fixture()
def client():
    from app import app
    from database import init_db
    init_db()
    return TestClient(app)


def _cleanup(client, scenario_id):
    client.delete(f"/api/scenarios/{scenario_id}")


def test_crud_roundtrip(client):
    resp = client.post("/api/scenarios", json=SCENARIO_PAYLOAD)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    sid = created["id"]
    try:
        assert created["name"] == "Term 1"
        assert len(created["teachers"]) == 2
        assert created["courses"][0]["max_per_day"] == 2
        assert created["preferences"]["gap_weight"] == 8.0

        got = client.get(f"/api/scenarios/{sid}").json()
        assert got == created

        listed = client.get("/api/scenarios").json()
        assert any(s["id"] == sid for s in listed)
        assert any(s["counts"]["courses"] == 2 for s in listed if s["id"] == sid)

        # Update: change required hours, drop a teacher
        updated = dict(SCENARIO_PAYLOAD)
        updated["name"] = "Term 1 (revised)"
        updated["courses"][0]["required_hours"] = 4
        resp = client.put(f"/api/scenarios/{sid}", json=updated)
        assert resp.status_code == 200
        got = client.get(f"/api/scenarios/{sid}").json()
        assert got["name"] == "Term 1 (revised)"
        assert got["courses"][0]["required_hours"] == 4
    finally:
        _cleanup(client, sid)
    assert client.get(f"/api/scenarios/{sid}").status_code == 404


def test_validation_rejects_bad_references(client):
    bad = {
        "name": "Bad",
        "teachers": [],
        "rooms": [],
        "class_groups": [],
        "courses": [{"id": "c1", "subject": "Math", "required_hours": 2,
                     "requires_lab": False, "allowed_teachers": ["t1"],
                     "class_group_id": "ghost"}],
    }
    resp = client.post("/api/scenarios", json=bad)
    assert resp.status_code == 400
    assert "unknown class group" in resp.json()["detail"]


def test_optimize_scenario_saves_schedule(client):
    resp = client.post("/api/scenarios", json=SCENARIO_PAYLOAD)
    sid = resp.json()["id"]
    try:
        result = client.post(f"/api/scenarios/{sid}/optimize").json()
        assert result["status"] == "success", result
        assert "schedule_id" in result
        assert result["stats"]["solve_time_seconds"] >= 0

        schedules = client.get(f"/api/scenarios/{sid}/schedules").json()
        assert len(schedules) == 1
        full = client.get(f"/api/scenarios/{sid}/schedules/{result['schedule_id']}").json()
        assert full["schedule"] == result["schedule"]
        assert all(e["class_group"] == "g1" for e in full["schedule"])

        # Run again -> second saved schedule
        client.post(f"/api/scenarios/{sid}/optimize")
        schedules = client.get(f"/api/scenarios/{sid}/schedules").json()
        assert len(schedules) == 2

        assert client.delete(
            f"/api/scenarios/{sid}/schedules/{result['schedule_id']}").status_code == 200
        schedules = client.get(f"/api/scenarios/{sid}/schedules").json()
        assert len(schedules) == 1
    finally:
        _cleanup(client, sid)


def test_async_optimize_job(client):
    resp = client.post("/api/scenarios", json=SCENARIO_PAYLOAD)
    sid = resp.json()["id"]
    try:
        accepted = client.post(f"/api/scenarios/{sid}/optimize?async=true").json()
        assert accepted["status"] == "accepted"
        job_id = accepted["job_id"]

        for _ in range(100):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] == "done":
                break
            time.sleep(0.05)
        assert job["status"] == "done", job
        assert job["result"]["status"] == "success"
        assert "schedule_id" in job

        schedules = client.get(f"/api/scenarios/{sid}/schedules").json()
        assert len(schedules) == 1
    finally:
        _cleanup(client, sid)


def test_delete_scenario_cascades_schedules(client):
    resp = client.post("/api/scenarios", json=SCENARIO_PAYLOAD)
    sid = resp.json()["id"]
    client.post(f"/api/scenarios/{sid}/optimize")
    assert len(client.get(f"/api/scenarios/{sid}/schedules").json()) == 1
    client.delete(f"/api/scenarios/{sid}")
    # schedules must be gone too
    assert client.get(f"/api/scenarios/{sid}/schedules").status_code == 404
    assert client.get(f"/api/scenarios/{sid}").status_code == 404


def test_stateless_optimize_still_works(client):
    resp = client.post("/api/optimize", json={
        "teachers": [{"id": "t1", "name": "Smith", "subject": ["Math"],
                      "available_days": ["Mon"], "max_hours_per_week": 5}],
        "rooms": [{"id": "r1", "capacity": 30, "is_lab": False}],
        "courses": [{"id": "c1", "subject": "Math", "required_hours": 1,
                     "requires_lab": False, "allowed_teachers": ["t1"]}],
    })
    assert resp.status_code == 200 and resp.json()["status"] == "success"
