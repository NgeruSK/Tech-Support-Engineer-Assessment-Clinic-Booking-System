from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .database import Base, SessionLocal, engine
from .exceptions import AlreadyCancelledError, ConflictError, NotFoundError, ValidationError
from .routers import appointments, doctors, patients
from .seed import seed_doctors

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Clinic Booking API", version="1.0.0")

app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(patients.router)


@app.on_event("startup")
def startup_seed() -> None:
    db = SessionLocal()
    try:
        seed_doctors(db)
    finally:
        db.close()


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(AlreadyCancelledError)
async def already_cancelled_handler(request: Request, exc: AlreadyCancelledError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})
