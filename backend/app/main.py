from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, command, day, google_auth, tasks, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Jarvis Task Scheduler", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(command.router)
app.include_router(day.router)
app.include_router(users.router)
app.include_router(google_auth.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
