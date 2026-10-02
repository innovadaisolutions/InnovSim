"""Local API serving persisted simulations and the built frontend, if present."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import field_validator

from .email_import import EmailImport, import_email
from .models import Run, Scenario, StrictModel, validate_identifier
from .storage import NotFoundError, Repository


class RunRequest(StrictModel):
    scenario_id: str

    _id = field_validator("scenario_id")(validate_identifier)


class RefineRequest(StrictModel):
    suggestion_id: str

    _id = field_validator("suggestion_id")(validate_identifier)


def create_app(database_path: str | Path | None = None) -> FastAPI:
    repository = Repository(database_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        repository.close()

    app = FastAPI(
        title="InnovSim local simulation API",
        version="0.1.0",
        lifespan=lifespan,
        description="Deterministic offline workflows, guarded mock tools and immutable comparison runs. No live business actions.",
    )
    app.state.repository = repository

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_, error: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "simulation", "adapter": "deterministic"}

    @app.get("/api/scenarios", response_model=list[Scenario])
    def list_scenarios():
        return repository.list_scenarios()

    @app.get("/api/scenarios/{scenario_id}", response_model=Scenario)
    def get_scenario(scenario_id: str):
        return repository.get_scenario(scenario_id)

    @app.post("/api/scenarios", response_model=Scenario)
    def save_scenario(scenario: Scenario):
        return repository.save_scenario(scenario)

    @app.get("/api/runs", response_model=list[Run])
    def list_runs():
        return repository.list_runs()

    @app.post("/api/runs", response_model=Run)
    def create_run(request: RunRequest):
        return repository.run_scenario(request.scenario_id)

    @app.get("/api/runs/{run_id}", response_model=Run)
    def get_run(run_id: str):
        return repository.get_run(run_id)

    @app.post("/api/runs/{run_id}/refine", response_model=Run)
    def refine_run(run_id: str, request: RefineRequest):
        try:
            return repository.refine_run(run_id, request.suggestion_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/import/email", response_model=Scenario)
    def import_email_scenario(request: EmailImport):
        try:
            return repository.save_scenario(import_email(request))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.api_route("/api", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.api_route(
        "/api/{unknown:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )
    def unknown_api(unknown: str = ""):
        raise HTTPException(status_code=404, detail="Unknown API endpoint.")

    dist = Path(
        os.environ.get("AW_WEB_DIST", str(Path(__file__).resolve().parents[2] / "web" / "dist"))
    ).resolve()

    @app.get("/{requested_path:path}", include_in_schema=False)
    def frontend(requested_path: str):
        target = (dist / requested_path).resolve()
        if not target.is_relative_to(dist):
            raise HTTPException(status_code=404, detail="File not found.")
        if target.is_file():
            return FileResponse(target)
        if (dist / "index.html").is_file() and not Path(requested_path).suffix:
            return FileResponse(dist / "index.html")
        if not requested_path:
            return {
                "project": "InnovSim",
                "mode": "simulation",
                "api": "/api/health",
                "docs": "/docs",
                "frontend": "Build web/dist to serve the browser interface.",
            }
        raise HTTPException(status_code=404, detail="File not found.")

    return app
