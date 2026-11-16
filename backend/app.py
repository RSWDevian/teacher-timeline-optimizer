from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from models import Teacher, Room, Course, ClassGroup, Preferences
from solver import solve_timetable
from api_scenarios import router as scenarios_router
from database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Teacher Timetable Optimizer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios_router)


class OptimizeRequest(BaseModel):
    teachers: List[Teacher]
    rooms: List[Room]
    courses: List[Course]
    class_groups: List[ClassGroup] = []
    preferences: Preferences = Preferences()


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running"}


@app.post("/api/optimize")
async def optimize_schedule(request: OptimizeRequest):
    try:
        return solve_timetable(
            request.teachers,
            request.rooms,
            request.courses,
            request.class_groups,
            request.preferences,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
