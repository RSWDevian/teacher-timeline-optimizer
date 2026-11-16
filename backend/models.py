from pydantic import BaseModel
from typing import List

class Teacher(BaseModel):
    id: str
    name: str
    subject: List[str]
    available_days: List[str]
    max_hours_per_week: int

class Room(BaseModel):
    id: str
    capacity: int
    is_lab: bool

class Course(BaseModel):
    id: str
    subject: str
    required_hours: int
    requires_lab: bool
    allowed_teachers: List[str]
    