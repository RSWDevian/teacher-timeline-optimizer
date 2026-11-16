from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from models import Teacher, Room, Course
from solver import solve_timetable # Uncommented

app = FastAPI(title="Teacher Timetable Optimizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running"}

@app.post("/api/optimize")
async def optimize_schedule(teachers: List[Teacher], rooms: List[Room], courses: List[Course]):
    try:
        # Execute the OR-Tools model
        schedule_result = solve_timetable(teachers, rooms, courses)
        return schedule_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))