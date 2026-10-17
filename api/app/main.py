import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.db import close_pool, open_pool
from app.http import register_handlers
from app.openapi_compat import as_openapi_30
from app.routers.admin import router as admin_router
from app.routers.cabinet import router as cabinet_router
from app.schemas import ErrorResponse, Health
from app.services.auth import ensure_bootstrap_admin

logger = logging.getLogger("lkbonch")

DESCRIPTION = """
Личный кабинет одного университета.

JSON в camelCase. Время — RFC3339 со смещением. Деньги и баллы — десятичные строки, не числа с плавающей точкой. Идентификаторы — UUID.

Вход: заголовок `Authorization: Bearer <accessToken>`. Refresh-токен приходит в теле и обновляется через `POST /api/v1/auth/refresh`. Куки не используются: мобильному клиенту они не нужны.

Ошибка всегда имеет вид `{"error": {"code", "message", "details"?}}`. Продолжение списка: `{"items", "nextCursor"}`. Повтор сообщения с тем же `clientMessageId` возвращает уже сохранённое сообщение.

Клиент Kotlin генерируется из этого документа (OpenAPI 3.0.3), например openapi-generator или Kiota.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.file_dir).mkdir(parents=True, exist_ok=True)
    pool = open_pool()
    app.state.pool = pool
    try:
        with pool.connection() as conn:
            ensure_bootstrap_admin(conn)
            conn.commit()
    except Exception:
        logger.exception("bootstrap admin was not created")
    yield
    close_pool()


app = FastAPI(
    title="Личный кабинет университета 2.0",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_version="3.0.3",
    lifespan=lifespan,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)

register_handlers(app)

origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(cabinet_router)
app.include_router(admin_router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = as_openapi_30(FastAPI.openapi(app))
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.get("/health", operation_id="health", response_model=Health)
def health(request: Request):
    try:
        with request.app.state.pool.connection() as conn:
            conn.execute("SELECT 1")
            conn.rollback()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
    return {"status": "ok", "database": "ok"}


@app.get("/api/v1/openapi.yaml", include_in_schema=False)
def design_contract() -> FileResponse:
    path = Path(__file__).resolve().parents[1] / "openapi.yaml"
    return FileResponse(path, media_type="application/yaml")
