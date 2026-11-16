import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


def utcnow_naive():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    created_at = Column(DateTime, default=utcnow_naive)
    preferences = Column(JSON, default=dict)

    teachers = relationship("TeacherRow", cascade="all, delete-orphan",
                            back_populates="scenario")
    rooms = relationship("RoomRow", cascade="all, delete-orphan",
                         back_populates="scenario")
    class_groups = relationship("ClassGroupRow", cascade="all, delete-orphan",
                                back_populates="scenario")
    courses = relationship("CourseRow", cascade="all, delete-orphan",
                           back_populates="scenario")
    schedules = relationship("SavedSchedule", cascade="all, delete-orphan",
                             back_populates="scenario")


class TeacherRow(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"),
                         nullable=False)
    ext_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    subject = Column(JSON, default=list)
    available_days = Column(JSON, default=list)
    max_hours_per_week = Column(Integer, nullable=False)
    unavailable_slots = Column(JSON, default=list)

    scenario = relationship("Scenario", back_populates="teachers")


class RoomRow(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"),
                         nullable=False)
    ext_id = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    is_lab = Column(Boolean, default=False)

    scenario = relationship("Scenario", back_populates="rooms")


class ClassGroupRow(Base):
    __tablename__ = "class_groups"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"),
                         nullable=False)
    ext_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    size = Column(Integer, nullable=False)

    scenario = relationship("Scenario", back_populates="class_groups")


class CourseRow(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"),
                         nullable=False)
    ext_id = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    required_hours = Column(Integer, nullable=False)
    requires_lab = Column(Boolean, default=False)
    allowed_teachers = Column(JSON, default=list)
    class_group_ext_id = Column(String, nullable=True)
    max_per_day = Column(Integer, nullable=True)

    scenario = relationship("Scenario", back_populates="courses")


class SavedSchedule(Base):
    __tablename__ = "saved_schedules"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"),
                         nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)
    status = Column(String, nullable=False)
    objective_value = Column(Float, nullable=True)
    stats = Column(JSON, default=dict)
    entries = Column(JSON, default=list)

    scenario = relationship("Scenario", back_populates="schedules")
