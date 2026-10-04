import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST, SEED_DEMO
from .database import Base, SessionLocal, engine
from .routers import auth, insights, planning, transactions

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if SEED_DEMO:
        from .demo import seed_demo

        with SessionLocal() as db:
            seed_demo(db)
    yield


app = FastAPI(title="FinSight API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, transactions.router, insights.router, planning.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# In production the built React app is served by FastAPI, so the whole thing deploys as one service.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = FRONTEND_DIST / path
        if path and file.is_file() and FRONTEND_DIST in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
