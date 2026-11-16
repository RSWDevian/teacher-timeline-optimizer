import datetime

from db_models import utcnow_naive
import threading
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

import db_models
from database import get_db
from models import (
    ClassGroup,
    Course,
    Preferences,
    Room,
    Teacher,
)
from solver import solve_timetable

router = APIRouter(prefix="/api")


# ---------- request / response schemas ----------

class ScenarioIn(BaseModel):
    name: str
    description: str = ""
    teachers: list[Teacher] = []
    rooms: list[Room] = []
    class_groups: list[ClassGroup] = []
    courses: list[Course] = []
    preferences: Preferences = Preferences()


# ---------- in-memory job registry (async solving) ----------

_JOBS = {}
_JOBS_LOCK = threading.Lock()


def _create_job() -> str:
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "pending", "scenario_id": None}
    return job_id


def _set_job(job_id: str, **fields):
    with _JOBS_LOCK:
        _JOBS[job_id].update(fields)


def _get_job(job_id: str):
    return _JOBS.get(job_id)


# ---------- row <-> model conversion ----------

def _row_to_teacher(row: db_models.TeacherRow) -> Teacher:
    return Teacher(
        id=row.ext_id, name=row.name, subject=row.subject or [],
        available_days=row.available_days or [],
        max_hours_per_week=row.max_hours_per_week,
        unavailable_slots=row.unavailable_slots or [],
    )


def _row_to_room(row: db_models.RoomRow) -> Room:
    return Room(id=row.ext_id, capacity=row.capacity, is_lab=bool(row.is_lab))


def _row_to_group(row: db_models.ClassGroupRow) -> ClassGroup:
    return ClassGroup(id=row.ext_id, name=row.name, size=row.size)


def _row_to_course(row: db_models.CourseRow) -> Course:
    return Course(
        id=row.ext_id, subject=row.subject, required_hours=row.required_hours,
        requires_lab=bool(row.requires_lab), allowed_teachers=row.allowed_teachers or [],
        class_group_id=row.class_group_ext_id, max_per_day=row.max_per_day,
    )


def scenario_to_dict(scenario: db_models.Scenario, full: bool = True) -> dict:
    data = {
        "id": scenario.id,
        "name": scenario.name,
        "description": scenario.description or "",
        "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
        "preferences": scenario.preferences or {},
        "counts": {
            "teachers": len(scenario.teachers),
            "rooms": len(scenario.rooms),
            "class_groups": len(scenario.class_groups),
            "courses": len(scenario.courses),
        },
    }
    if full:
        data.update({
            "teachers": [
                {"id": t.ext_id, "name": t.name, "subject": t.subject,
                 "available_days": t.available_days,
                 "max_hours_per_week": t.max_hours_per_week,
                 "unavailable_slots": t.unavailable_slots}
                for t in scenario.teachers
            ],
            "rooms": [
                {"id": r.ext_id, "capacity": r.capacity, "is_lab": bool(r.is_lab)}
                for r in scenario.rooms
            ],
            "class_groups": [
                {"id": g.ext_id, "name": g.name, "size": g.size}
                for g in scenario.class_groups
            ],
            "courses": [
                {"id": c.ext_id, "subject": c.subject,
                 "required_hours": c.required_hours,
                 "requires_lab": bool(c.requires_lab),
                 "allowed_teachers": c.allowed_teachers,
                 "class_group_id": c.class_group_ext_id,
                 "max_per_day": c.max_per_day}
                for c in scenario.courses
            ],
        })
    return data


def _validate(scenario_in: ScenarioIn):
    errors = []
    teacher_ids = [t.id for t in scenario_in.teachers]
    group_ids = [g.id for g in scenario_in.class_groups]
    for label, ids in (("teacher", teacher_ids), ("class group", group_ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            errors.append(f"Duplicate {label} id(s): {', '.join(sorted(dupes))}")
    group_set = set(group_ids)
    teacher_set = set(teacher_ids)
    for c in scenario_in.courses:
        if c.required_hours < 0:
            errors.append(f"Course {c.id} has negative required_hours.")
        if c.max_per_day is not None and c.max_per_day < 1:
            errors.append(f"Course {c.id} max_per_day must be >= 1.")
        unknown = [t for t in c.allowed_teachers if t not in teacher_set]
        if unknown:
            errors.append(f"Course {c.id} references unknown teacher(s): {', '.join(unknown)}.")
        if c.class_group_id and c.class_group_id not in group_set:
            errors.append(f"Course {c.id} references unknown class group '{c.class_group_id}'.")
    if errors:
        raise HTTPException(status_code=400, detail=" | ".join(errors))


def _replace_entities(db: Session, scenario: db_models.Scenario, data: ScenarioIn):
    scenario.teachers = []
    scenario.rooms = []
    scenario.class_groups = []
    scenario.courses = []
    db.flush()
    for t in data.teachers:
        scenario.teachers.append(db_models.TeacherRow(
            ext_id=t.id, name=t.name, subject=t.subject,
            available_days=t.available_days, max_hours_per_week=t.max_hours_per_week,
            unavailable_slots=t.unavailable_slots))
    for r in data.rooms:
        scenario.rooms.append(db_models.RoomRow(ext_id=r.id, capacity=r.capacity, is_lab=r.is_lab))
    for g in data.class_groups:
        scenario.class_groups.append(db_models.ClassGroupRow(ext_id=g.id, name=g.name, size=g.size))
    for c in data.courses:
        scenario.courses.append(db_models.CourseRow(
            ext_id=c.id, subject=c.subject, required_hours=c.required_hours,
            requires_lab=c.requires_lab, allowed_teachers=c.allowed_teachers,
            class_group_ext_id=c.class_group_id, max_per_day=c.max_per_day))


def _get_scenario_or_404(db: Session, scenario_id: int) -> db_models.Scenario:
    scenario = db.get(db_models.Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found.")
    return scenario


def _solver_inputs(scenario: db_models.Scenario):
    teachers = [_row_to_teacher(t) for t in scenario.teachers]
    rooms = [_row_to_room(r) for r in scenario.rooms]
    groups = [_row_to_group(g) for g in scenario.class_groups]
    courses = [_row_to_course(c) for c in scenario.courses]
    prefs = Preferences(**(scenario.preferences or {}))
    return teachers, rooms, courses, groups, prefs


def _save_schedule(db: Session, scenario: db_models.Scenario, result: dict) -> db_models.SavedSchedule:
    count = db.query(db_models.SavedSchedule).filter_by(scenario_id=scenario.id).count()
    saved = db_models.SavedSchedule(
        scenario_id=scenario.id,
        name=f"Schedule {count + 1} - {utcnow_naive().strftime('%Y-%m-%d %H:%M')}",
        status=result["status"],
        objective_value=result.get("objective_value"),
        stats=result.get("stats", {}),
        entries=result.get("schedule", []),
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return saved


def schedule_to_dict(saved: db_models.SavedSchedule) -> dict:
    return {
        "id": saved.id,
        "scenario_id": saved.scenario_id,
        "name": saved.name,
        "created_at": saved.created_at.isoformat() if saved.created_at else None,
        "status": saved.status,
        "objective_value": saved.objective_value,
        "stats": saved.stats or {},
        "schedule": saved.entries or [],
    }


# ---------- background job worker ----------

def _run_optimization_job(scenario_id: int, job_id: str):
    from database import SessionLocal
    db = SessionLocal()
    try:
        _set_job(job_id, status="running")
        scenario = db.get(db_models.Scenario, scenario_id)
        if not scenario:
            _set_job(job_id, status="failed", error=f"Scenario {scenario_id} not found.")
            return
        teachers, rooms, courses, groups, prefs = _solver_inputs(scenario)
        result = solve_timetable(teachers, rooms, courses, groups, prefs)
        response = {"result": result}
        if result["status"] == "success":
            saved = _save_schedule(db, scenario, result)
            response["schedule_id"] = saved.id
        _set_job(job_id, status="done", **response)
    except Exception as e:
        _set_job(job_id, status="failed", error=str(e))
    finally:
        db.close()


# ---------- endpoints ----------

@router.post("/scenarios", status_code=201)
def create_scenario(data: ScenarioIn, db: Session = Depends(get_db)):
    _validate(data)
    scenario = db_models.Scenario(name=data.name, description=data.description,
                                  preferences=data.preferences.model_dump())
    db.add(scenario)
    db.flush()
    _replace_entities(db, scenario, data)
    db.commit()
    db.refresh(scenario)
    return scenario_to_dict(scenario)


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)):
    scenarios = db.query(db_models.Scenario).order_by(db_models.Scenario.id).all()
    return [scenario_to_dict(s, full=False) for s in scenarios]


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    return scenario_to_dict(_get_scenario_or_404(db, scenario_id))


@router.put("/scenarios/{scenario_id}")
def update_scenario(scenario_id: int, data: ScenarioIn, db: Session = Depends(get_db)):
    _validate(data)
    scenario = _get_scenario_or_404(db, scenario_id)
    scenario.name = data.name
    scenario.description = data.description
    scenario.preferences = data.preferences.model_dump()
    _replace_entities(db, scenario, data)
    db.commit()
    db.refresh(scenario)
    return scenario_to_dict(scenario)


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = _get_scenario_or_404(db, scenario_id)
    db.delete(scenario)
    db.commit()
    return {"status": "deleted", "id": scenario_id}


@router.post("/scenarios/{scenario_id}/optimize")
def optimize_scenario(scenario_id: int, background: BackgroundTasks,
                      async_mode: bool = Query(False, alias="async"),
                      db: Session = Depends(get_db)):
    scenario = _get_scenario_or_404(db, scenario_id)
    if async_mode:
        job_id = _create_job()
        _set_job(job_id, scenario_id=scenario_id)
        background.add_task(_run_optimization_job, scenario_id, job_id)
        return {"status": "accepted", "job_id": job_id}
    teachers, rooms, courses, groups, prefs = _solver_inputs(scenario)
    result = solve_timetable(teachers, rooms, courses, groups, prefs)
    response = dict(result)
    if result["status"] == "success":
        saved = _save_schedule(db, scenario, result)
        response["schedule_id"] = saved.id
    return response


@router.get("/scenarios/{scenario_id}/schedules")
def list_schedules(scenario_id: int, db: Session = Depends(get_db)):
    _get_scenario_or_404(db, scenario_id)
    saved = (db.query(db_models.SavedSchedule)
             .filter_by(scenario_id=scenario_id)
             .order_by(db_models.SavedSchedule.id).all())
    return [schedule_to_dict(s) for s in saved]


@router.get("/scenarios/{scenario_id}/schedules/{schedule_id}")
def get_schedule(scenario_id: int, schedule_id: int, db: Session = Depends(get_db)):
    _get_scenario_or_404(db, scenario_id)
    saved = db.get(db_models.SavedSchedule, schedule_id)
    if not saved or saved.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found.")
    return schedule_to_dict(saved)


@router.delete("/scenarios/{scenario_id}/schedules/{schedule_id}")
def delete_schedule(scenario_id: int, schedule_id: int, db: Session = Depends(get_db)):
    _get_scenario_or_404(db, scenario_id)
    saved = db.get(db_models.SavedSchedule, schedule_id)
    if not saved or saved.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found.")
    db.delete(saved)
    db.commit()
    return {"status": "deleted", "id": schedule_id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job
