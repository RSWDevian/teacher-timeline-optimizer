from ortools.sat.python import cp_model

def solve_timetable(teachers_data, rooms_data, courses_data):
    model = cp_model.CpModel()
    
    # Define the time grid (e.g., 5 days, 4 periods per day)
    num_days = 5
    num_periods = 4
    
    # Extract ID lists for iteration
    teachers = [t.id for t in teachers_data]
    rooms = [r.id for r in rooms_data]
    courses = [c.id for c in courses_data]
    
    # 1. Initialize Variables
    # shifts[(c, t, r, d, p)] = 1 if course c is taught by teacher t in room r on day d period p
    shifts = {}
    for c in courses:
        for t in teachers:
            for r in rooms:
                for d in range(num_days):
                    for p in range(num_periods):
                        shifts[(c, t, r, d, p)] = model.NewBoolVar(f'shift_{c}_{t}_{r}_{d}_{p}')
    
    # 2. Hard Constraints
    # A teacher cannot be double-booked in a single time slot
    for t in teachers:
        for d in range(num_days):
            for p in range(num_periods):
                model.AddAtMostOne(
                    shifts[(c, t, r, d, p)] for c in courses for r in rooms)
                    
    # A room cannot be double-booked / exceeded
    for r in rooms:
        for d in range(num_days):
            for p in range(num_periods):
                model.AddAtMostOne(
                    shifts[(c, t, r, d, p)] for c in courses for t in teachers)
                    
    # Core curriculum hours must be fulfilled for each course
    for course_obj in courses_data:
        c = course_obj.id
        required_hours = course_obj.required_hours
        model.Add(
            sum(shifts[(c, t, r, d, p)]
                for t in teachers
                for r in rooms
                for d in range(num_days)
                for p in range(num_periods)) == required_hours)
                
    # 3. Solve the Model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Extract the timetable schedule
        schedule = []
        for c in courses:
            for t in teachers:
                for r in rooms:
                    for d in range(num_days):
                        for p in range(num_periods):
                            if solver.Value(shifts[(c, t, r, d, p)]) == 1:
                                schedule.append({
                                    'course': c,
                                    'teacher': t,
                                    'room': r,
                                    'day': f'Day {d+1}',
                                    'period': f'Period {p+1}'
                                })
        return {"status": "success", "schedule": schedule, "objective_value": solver.ObjectiveValue()}
    else:
        return {"status": "error", "message": "No feasible schedule found with the given constraints."}