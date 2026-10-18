"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.build_info import get_build_info
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routes import admin, internship, teacher
from app.services.bootstrap import bootstrap_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create database tables and seed baseline data when the app starts."""

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        bootstrap_database(db)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
# Session cookies are needed for the admin login.
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=False, same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# The public teacher flow lives at `/`, the internship planner at `/practiques`,
# and admin stays under `/admin`.
app.include_router(teacher.router)
app.include_router(internship.router)
app.include_router(admin.router)


@app.get("/build-info.json", include_in_schema=False)
def build_info() -> JSONResponse:
    """Expose the deployed commit, environment and latest release for tooling."""

    return JSONResponse(get_build_info(), headers={"Cache-Control": "no-cache"})
