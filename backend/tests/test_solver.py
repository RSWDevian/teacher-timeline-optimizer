from models import Teacher, Room, Course, ClassGroup, Preferences
from solver import solve_timetable, DAYS


def make_teacher(**over):
    defaults = dict(id="t1", name="Smith", subject=["Math"],
                    available_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
                    max_hours_per_week=20, unavailable_slots=[])
    defaults.update(over)
    return Teacher(**defaults)


def make_room(**over):
    defaults = dict(id="r1", capacity=30, is_lab=False)
    defaults.update(over)
    return Room(**defaults)


def make_group(**over):
    defaults = dict(id="g1", name="Grade 9-A", size=25)
    defaults.update(over)
    return ClassGroup(**defaults)


def make_course(**over):
    defaults = dict(id="c1", subject="Math", required_hours=3, requires_lab=False,
                    allowed_teachers=["t1"], class_group_id="g1", max_per_day=None)
    defaults.update(over)
    return Course(**defaults)


def solve(teachers, rooms, courses, groups=None, prefs=None):
    return solve_timetable(teachers, rooms, courses, groups or [], prefs)


def test_happy_path_with_all_features():
    result = solve(
        [make_teacher(unavailable_slots=["Mon-1"]),
         make_teacher(id="t2", name="Jones", subject=["Chemistry"], max_hours_per_week=10)],
        [make_room(), make_room(id="r2", capacity=32, is_lab=True)],
        [make_course(),
         make_course(id="c2", subject="Chemistry", required_hours=2, requires_lab=True,
                     allowed_teachers=["t2"])],
        [make_group()],
    )
    assert result["status"] == "success", result
    schedule = result["schedule"]
    # Lab course only in lab room with its teacher
    assert all(s["room"] == "r2" and s["teacher"] == "t2" for s in schedule if s["course"] == "c2")
    # Subject/allowed-teacher matching
    assert all(s["teacher"] == "t1" for s in schedule if s["course"] == "c1")
    # Unavailable slot respected
    assert not any(s["teacher"] == "t1" and s["day"] == "Mon" and s["period"] == "Period 1"
                   for s in schedule)
    # Class group attached to output
    assert all(s["class_group"] == "g1" for s in schedule)
    assert "objective_value" in result and "stats" in result


def test_class_group_not_double_booked():
    courses = [make_course(), make_course(id="c2", required_hours=4, max_per_day=None)]
    result = solve([make_teacher()], [make_room()], courses, [make_group()])
    assert result["status"] == "success"
    seen = {}
    for s in result["schedule"]:
        key = (s["day"], s["period"])
        assert key not in seen, f"class group double-booked at {key}"
        seen[key] = s["course"]


def test_room_capacity_respected():
    # Group of 50 but only a 30-seat room -> course impossible
    result = solve([make_teacher()], [make_room(capacity=30)],
                   [make_course()], [make_group(size=50)])
    assert result["status"] == "error"
    assert "no eligible room" in result["message"]


def test_unknown_class_group_error():
    result = solve([make_teacher()], [make_room()],
                   [make_course(class_group_id="ghost")], [make_group()])
    assert result["status"] == "error"
    assert "unknown class group" in result["message"]


def test_max_per_day_respected():
    result = solve([make_teacher()], [make_room()],
                   [make_course(required_hours=3, max_per_day=1)], [make_group()])
    assert result["status"] == "success"
    per_day = {}
    for s in result["schedule"]:
        per_day[s["day"]] = per_day.get(s["day"], 0) + 1
    assert all(count <= 1 for count in per_day.values())
    assert sum(per_day.values()) == 3


def test_gap_minimization_prefers_adjacent_periods():
    # With spread disabled, a 2-hour course should occupy two ADJACENT periods
    # on one day rather than leaving a gap (e.g. Mon P1 + Mon P3).
    prefs = Preferences(gap_weight=10.0, spread_weight=0.0, balance_weight=0.0)
    result = solve([make_teacher()], [make_room()],
                   [make_course(required_hours=2)], [make_group()], prefs)
    assert result["status"] == "success"
    sessions = [(DAYS.index(s["day"]), int(s["period"].split()[1]) - 1)
                for s in result["schedule"]]
    assert len(sessions) == 2
    same_day = sessions[0][0] == sessions[1][0]
    if same_day:
        assert abs(sessions[0][1] - sessions[1][1]) == 1, f"gap found: {sessions}"


def test_teacher_load_balanced():
    prefs = Preferences(balance_weight=1.0, gap_weight=0.0, spread_weight=0.0)
    result = solve(
        [make_teacher(), make_teacher(id="t2", name="Wesson")],
        [make_room()],
        [make_course(required_hours=4, allowed_teachers=["t1", "t2"])],
        [make_group()],
        prefs,
    )
    assert result["status"] == "success"
    per_teacher = {}
    for s in result["schedule"]:
        per_teacher[s["teacher"]] = per_teacher.get(s["teacher"], 0) + 1
    assert per_teacher.get("t1", 0) == 2 and per_teacher.get("t2", 0) == 2


def test_infeasible_conflict_explained():
    # Two courses for one class group; both teachers available only Monday
    # -> 6 hours needed but only 4 Monday periods exist.
    result = solve(
        [make_teacher(available_days=["Mon"], max_hours_per_week=10),
         make_teacher(id="t2", name="Jones", subject=["Chemistry"],
                      available_days=["Mon"], max_hours_per_week=10)],
        [make_room()],
        [make_course(required_hours=3),
         make_course(id="c2", subject="Chemistry", required_hours=3,
                     allowed_teachers=["t2"])],
        [make_group()],
    )
    assert result["status"] == "error"
    assert "cannot all be scheduled together" in result["message"]
    assert "c1" in result["message"] and "c2" in result["message"]


def test_group_workload_precheck():
    result = solve(
        [make_teacher(), make_teacher(id="t2", name="Jones", subject=["Chemistry"])],
        [make_room()],
        [make_course(required_hours=15),
         make_course(id="c2", subject="Chemistry", required_hours=15,
                     allowed_teachers=["t2"])],
        [make_group()],
    )
    assert result["status"] == "error"
    assert "only has 20 periods" in result["message"]


def test_api_accepts_new_payload():
    from fastapi.testclient import TestClient
    from app import app
    client = TestClient(app)
    resp = client.post("/api/optimize", json={
        "teachers": [{"id": "t1", "name": "Smith", "subject": ["Math"],
                      "available_days": ["Mon", "Tue"], "max_hours_per_week": 15}],
        "rooms": [{"id": "r1", "capacity": 30, "is_lab": False}],
        "courses": [{"id": "c1", "subject": "Math", "required_hours": 2,
                     "requires_lab": False, "allowed_teachers": ["t1"],
                     "class_group_id": "g1"}],
        "class_groups": [{"id": "g1", "name": "Grade 9-A", "size": 25}],
        "preferences": {"gap_weight": 5.0, "spread_weight": 2.0},
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert all(s["class_group"] == "g1" for s in data["schedule"])

    # Old payload shape (no class_groups/preferences) still works
    resp_old = client.post("/api/optimize", json={
        "teachers": [{"id": "t1", "name": "Smith", "subject": ["Math"],
                      "available_days": ["Mon"], "max_hours_per_week": 15}],
        "rooms": [{"id": "r1", "capacity": 30, "is_lab": False}],
        "courses": [{"id": "c1", "subject": "Math", "required_hours": 1,
                     "requires_lab": False, "allowed_teachers": ["t1"]}],
    })
    assert resp_old.status_code == 200 and resp_old.json()["status"] == "success"
