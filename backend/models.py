from pydantic import BaseModel
from typing import List, Optional


class Teacher(BaseModel):
    id: str
    name: str
    subject: List[str]
    available_days: List[str]
    max_hours_per_week: int
    unavailable_slots: List[str] = []  # e.g. ["Mon-1", "Wed-3"]


class Room(BaseModel):
    id: str
    capacity: int
    is_lab: bool


class ClassGroup(BaseModel):
    id: str
    name: str
    size: int


class Course(BaseModel):
    id: str
    subject: str
    required_hours: int
    requires_lab: bool
    allowed_teachers: List[str]
    class_group_id: Optional[str] = None
    max_per_day: Optional[int] = None  # cap sessions per day, None = unlimited


class Preferences(BaseModel):
    balance_weight: float = 1.0    # penalty per hour of teacher max load
    gap_weight: float = 10.0       # penalty per idle period inside a class group's day
    spread_weight: float = 3.0     # penalty per session beyond 1 per day for a course
    time_limit_seconds: float = 30.0
