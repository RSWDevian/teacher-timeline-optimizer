"""Benchmark the CP-SAT solver on synthetic scenarios of increasing size.

Run from the backend directory:  python benchmark.py
"""

import random
import time

from models import ClassGroup, Course, Preferences, Room, Teacher
from solver import solve_timetable, DAYS

random.seed(42)

SUBJECTS = ["Math", "Physics", "Chemistry", "Biology", "History", "Geography", "English"]

SCALES = [
    # (teachers, rooms, class_groups, courses, label)
    (5, 4, 2, 8, "small"),
    (10, 8, 5, 25, "medium"),
    (20, 14, 10, 50, "large"),
    (35, 25, 18, 90, "xlarge"),
]


def build(teachers_n, rooms_n, groups_n, courses_n):
    groups = [ClassGroup(id=f"g{i}", name=f"Class {i + 1}", size=20 + i % 10)
              for i in range(groups_n)]
    rooms = [Room(id=f"r{i}", capacity=30, is_lab=(i % 3 == 0)) for i in range(rooms_n)]

    # Each teacher gets a disjoint pair of subjects so course->teacher matching is unique-ish
    teacher_subjects = {}
    for i in range(teachers_n):
        s1 = SUBJECTS[i % len(SUBJECTS)]
        s2 = SUBJECTS[(i + 3) % len(SUBJECTS)]
        teacher_subjects[f"t{i}"] = {s1, s2}
    teachers = [
        Teacher(id=tid, name=f"Teacher {i}", subject=sorted(subs),
                available_days=DAYS, max_hours_per_week=20, unavailable_slots=[])
        for i, (tid, subs) in enumerate(teacher_subjects.items())
    ]

    def teachers_of(subject):
        return [tid for tid, subs in teacher_subjects.items() if subject in subs]

    courses = []
    for i in range(courses_n):
        subject = SUBJECTS[i % len(SUBJECTS)]
        group = groups[i % groups_n]
        lab = bool(random.random() < 0.25)
        candidates = teachers_of(subject)
        if not candidates:
            continue
        courses.append(Course(
            id=f"c{i}", subject=subject,
            required_hours=random.choice([2, 3]),
            requires_lab=lab,
            allowed_teachers=random.sample(candidates, k=min(2, len(candidates))),
            class_group_id=group.id,
            max_per_day=2,
        ))

    # Fix lab demand: lab courses need lab rooms with enough capacity
    labs = [r for r in rooms if r.is_lab]
    lab_demand = sum(c.required_hours for c in courses if c.requires_lab)
    if labs:
        capacity = len(labs) * len(DAYS) * 4
        if lab_demand > capacity * 0.9:
            # trim lab hours to fit
            budget = int(capacity * 0.8)
            for c in courses:
                if c.requires_lab and budget >= 0:
                    take = min(c.required_hours, budget)
                    c.required_hours = take
                    budget -= take
                    if take == 0:
                        c.requires_lab = False

    prefs = Preferences(balance_weight=1, gap_weight=10, spread_weight=3, time_limit_seconds=60)
    return teachers, rooms, courses, groups, prefs


def main():
    print(f"{'scale':<8} {'teachers':>9} {'rooms':>6} {'groups':>7} {'courses':>8} "
          f"{'hours':>6} {'status':>10} {'obj':>8} {'solve_s':>8}")
    print("-" * 78)
    for teachers_n, rooms_n, groups_n, courses_n, label in SCALES:
        teachers, rooms, courses, groups, prefs = build(teachers_n, rooms_n, groups_n, courses_n)
        if not courses:
            print(f"{label:<8} generation failed (no eligible courses)")
            continue
        start = time.perf_counter()
        result = solve_timetable(teachers, rooms, courses, groups, prefs)
        elapsed = time.perf_counter() - start
        status = result.get("status", "?")
        obj = result.get("objective_value", "-")
        obj = f"{obj:.1f}" if isinstance(obj, float) else obj
        hours = sum(c.required_hours for c in courses)
        print(f"{label:<8} {len(teachers):>9} {len(rooms):>6} {len(groups):>7} "
              f"{len(courses):>8} {hours:>6} {status:>10} {str(obj):>8} {elapsed:>8.2f}")


if __name__ == "__main__":
    main()
