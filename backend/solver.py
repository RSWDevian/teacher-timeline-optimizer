from ortools.sat.python import cp_model

from models import Preferences

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def _parse_slot(slot, num_periods):
    # "Mon-2" -> (0, 1); returns None if malformed or out of range
    try:
        day, period = slot.rsplit("-", 1)
        d = DAYS.index(day)
        p = int(period) - 1
        if 0 <= p < num_periods:
            return (d, p)
    except (ValueError, AttributeError):
        pass
    return None


def solve_timetable(teachers_data, rooms_data, courses_data,
                    class_groups_data=None, preferences=None):
    class_groups_data = class_groups_data or []
    prefs = preferences or Preferences()
    model = cp_model.CpModel()

    num_days = 5
    num_periods = 4

    teachers_by_id = {t.id: t for t in teachers_data}
    rooms_by_id = {r.id: r for r in rooms_data}
    groups_by_id = {g.id: g for g in class_groups_data}

    problems = []

    # Eligibility
    class_size = {
        c.id: groups_by_id[c.class_group_id].size
        if c.class_group_id in groups_by_id else None
        for c in courses_data
    }

    def eligible_teachers(c):
        allowed = set(c.allowed_teachers)
        return [t for t in teachers_by_id.values()
                if t.id in allowed and c.subject in t.subject]

    def eligible_rooms(c):
        rooms = list(rooms_by_id.values())
        if c.requires_lab:
            rooms = [r for r in rooms if r.is_lab]
        size = class_size.get(c.id)
        if size is not None:
            rooms = [r for r in rooms if r.capacity >= size]
        return rooms

    def teacher_slot_ok(t_obj, d, p):
        if t_obj.available_days and DAYS[d] not in t_obj.available_days:
            return False
        for slot in t_obj.unavailable_slots:
            if _parse_slot(slot, num_periods) == (d, p):
                return False
        return True

    eligible_t = {c.id: eligible_teachers(c) for c in courses_data}
    eligible_r = {c.id: eligible_rooms(c) for c in courses_data}

    # Infeasibility pre-checks (arithmetic, cheap)
    for c in courses_data:
        if c.class_group_id and c.class_group_id not in groups_by_id:
            problems.append(f"Course {c.id} references unknown class group '{c.class_group_id}'.")
        if not eligible_t[c.id]:
            problems.append(f"Course {c.id} ({c.subject}) has no eligible teacher "
                            "(check allowed_teachers and subject match).")
        if not eligible_r[c.id]:
            problems.append(f"Course {c.id} has no eligible room "
                            "(lab requirement or room capacity too small).")

    group_courses = {}
    for c in courses_data:
        if c.class_group_id:
            group_courses.setdefault(c.class_group_id, []).append(c.id)

    for gid, hours_needed in _hours_per_group(courses_data).items():
        if hours_needed > num_days * num_periods:
            problems.append(f"Class group {gid} needs {hours_needed} hours but the week only has "
                            f"{num_days * num_periods} periods.")

    lab_rooms = [r for r in rooms_by_id.values() if r.is_lab]
    lab_hours = sum(c.required_hours for c in courses_data if c.requires_lab)
    if lab_rooms and lab_hours > len(lab_rooms) * num_days * num_periods:
        problems.append(f"Lab courses need {lab_hours} hours but the labs only offer "
                        f"{len(lab_rooms) * num_days * num_periods} periods.")

    for c in courses_data:
        slots = sum(1 for t_obj in eligible_t[c.id]
                    for d in range(num_days) for p in range(num_periods)
                    if teacher_slot_ok(t_obj, d, p))
        combos = slots * len(eligible_r[c.id])
        if c.required_hours > combos:
            problems.append(f"Course {c.id} needs {c.required_hours} hours but teacher "
                            f"availability/rooms only allow {combos} distinct slots.")

    if problems:
        return {"status": "error", "message": " | ".join(problems)}

    # 1. Initialize Variables
    # shifts[(c, t, r, d, p)] = 1 if course c is taught by teacher t in room r on day d period p
    shifts = {}
    for c in courses_data:
        for t_obj in eligible_t[c.id]:
            for r_obj in eligible_r[c.id]:
                for d in range(num_days):
                    for p in range(num_periods):
                        if teacher_slot_ok(t_obj, d, p):
                            key = (c.id, t_obj.id, r_obj.id, d, p)
                            shifts[key] = model.NewBoolVar(
                                f'shift_{c.id}_{t_obj.id}_{r_obj.id}_{d}_{p}')

    def shifts_where(c=None, t=None, r=None, d=None, p=None):
        return [var for (cc, tt, rr, dd, pp), var in shifts.items()
                if (c is None or cc == c)
                and (t is None or tt == t)
                and (r is None or rr == r)
                and (d is None or dd == d)
                and (p is None or pp == p)]

    # 2. Hard Constraints
    # A teacher cannot be double-booked in a single time slot
    for t in teachers_by_id:
        for d in range(num_days):
            for p in range(num_periods):
                here = shifts_where(t=t, d=d, p=p)
                if here:
                    model.AddAtMostOne(here)

    # A room cannot be double-booked / exceeded
    for r in rooms_by_id:
        for d in range(num_days):
            for p in range(num_periods):
                here = shifts_where(r=r, d=d, p=p)
                if here:
                    model.AddAtMostOne(here)

    # A class group (its students) cannot be double-booked
    for gid, cids in group_courses.items():
        for d in range(num_days):
            for p in range(num_periods):
                here = shifts_where(d=d, p=p)
                here = [v for (cc, tt, rr, dd, pp), v in shifts.items()
                        if cc in cids and dd == d and pp == p]
                if here:
                    model.AddAtMostOne(here)

    # Core curriculum hours must be fulfilled for each course.
    # Each course's hours constraint is an assumption literal so that,
    # if the model is UNSAT, we can report exactly which courses conflict.
    course_assumptions = {}
    for c in courses_data:
        a = model.NewBoolVar(f'assume_{c.id}')
        course_assumptions[c.id] = a
        model.Add(sum(shifts_where(c=c.id)) == c.required_hours).OnlyEnforceIf(a)
    model.AddAssumptions(list(course_assumptions.values()))

    # Teachers cannot exceed their weekly hour limit
    for t_id, t_obj in teachers_by_id.items():
        here = shifts_where(t=t_id)
        if here:
            model.Add(sum(here) <= t_obj.max_hours_per_week)

    # Course sessions per day cap
    for c in courses_data:
        if c.max_per_day is None:
            continue
        for d in range(num_days):
            here = shifts_where(c=c.id, d=d)
            if here:
                model.Add(sum(here) <= c.max_per_day)

    # 3. Soft Constraints / Objective
    # 3a. Class-group gap detection: an idle period between activities on the same day
    busy = {}
    used_after = {}
    gaps = []
    for gid, cids in group_courses.items():
        for d in range(num_days):
            for p in range(num_periods):
                b = model.NewBoolVar(f'busy_{gid}_{d}_{p}')
                here = [v for (cc, tt, rr, dd, pp), v in shifts.items()
                        if cc in cids and dd == d and pp == p]
                if here:
                    model.AddMaxEquality(b, here)
                else:
                    model.Add(b == 0)
                busy[(gid, d, p)] = b
            for p in reversed(range(num_periods)):
                ua = model.NewBoolVar(f'used_after_{gid}_{d}_{p}')
                if p == num_periods - 1:
                    model.Add(ua == 0)
                else:
                    model.AddMaxEquality(ua, [busy[(gid, d, p + 1)],
                                              used_after[(gid, d, p + 1)]])
                used_after[(gid, d, p)] = ua
            for p in range(1, num_periods):
                g = model.NewBoolVar(f'gap_{gid}_{d}_{p}')
                # g is forced to 1 exactly when the period is idle but has
                # activity both before and after it on the same day
                model.Add(g >= busy[(gid, d, p - 1)] - busy[(gid, d, p)]
                          + used_after[(gid, d, p)] - 1)
                gaps.append(g)

    # 3b. Spread: penalize each session of a course beyond 1 per day
    overs = []
    for c in courses_data:
        for d in range(num_days):
            over = model.NewIntVar(0, c.required_hours, f'over_{c.id}_{d}')
            here = shifts_where(c=c.id, d=d)
            model.Add(over >= sum(here) - 1) if here else model.Add(over == 0)
            overs.append(over)

    # 3c. Teacher load balancing: minimize the max weekly load
    terms = []
    if teachers_by_id:
        max_hours = max(t_obj.max_hours_per_week for t_obj in teachers_by_id.values())
        loads = []
        for t_id in teachers_by_id:
            load = model.NewIntVar(0, max_hours, f'load_{t_id}')
            here = shifts_where(t=t_id)
            if here:
                model.Add(load == sum(here))
            else:
                model.Add(load == 0)
            loads.append(load)
        max_load = model.NewIntVar(0, max_hours, 'max_load')
        model.AddMaxEquality(max_load, loads)
        terms.append(prefs.balance_weight * max_load)
    terms += [prefs.gap_weight * g for g in gaps]
    terms += [prefs.spread_weight * o for o in overs]
    if terms:
        model.Minimize(sum(terms))

    # 4. Solve the Model
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = prefs.time_limit_seconds
    solver.parameters.num_workers = 8
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        group_of = {c.id: c.class_group_id for c in courses_data}
        schedule = []
        for (c, t, r, d, p), var in shifts.items():
            if solver.Value(var) == 1:
                schedule.append({
                    'course': c,
                    'teacher': t,
                    'room': r,
                    'class_group': group_of.get(c),
                    'day': DAYS[d],
                    'period': f'Period {p + 1}'
                })
        result = {
            "status": "success",
            "schedule": schedule,
            "stats": {
                "solve_time_seconds": round(solver.WallTime(), 3),
                "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
            },
        }
        if model.Proto().objective:
            result["objective_value"] = solver.ObjectiveValue()
        return result

    if status == cp_model.INFEASIBLE and course_assumptions:
        index_to_course = {a.Index(): cid for cid, a in course_assumptions.items()}
        conflicting = set()
        for lit in solver.SufficientAssumptionsForInfeasibility():
            cid = index_to_course.get(lit)
            if cid is None and lit % 2 == 1:
                cid = index_to_course.get(lit // 2)
            if cid:
                conflicting.add(cid)
        if conflicting:
            return {
                "status": "error",
                "message": "No feasible schedule. These courses cannot all be "
                           f"scheduled together: {', '.join(sorted(conflicting))}."
            }

    return {"status": "error", "message": "No feasible schedule found with the given constraints."}


def _hours_per_group(courses_data):
    hours = {}
    for c in courses_data:
        if c.class_group_id:
            hours[c.class_group_id] = hours.get(c.class_group_id, 0) + c.required_hours
    return hours
