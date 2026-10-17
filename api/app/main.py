import os
from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(
    title="Личный кабинет университета 2.0",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

origins = [item.strip() for item in os.environ.get("CORS_ORIGINS", "").split(",") if item.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health() -> JSONResponse:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
    return JSONResponse({"status": "ok", "database": "ok"})


@app.get("/api/v1/openapi.yaml")
def openapi_contract() -> FileResponse:
    path = Path(__file__).resolve().parents[1] / "openapi.yaml"
    return FileResponse(path, media_type="application/yaml")
