import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import Error as DbError
from psycopg.errors import CheckViolation, ExclusionViolation, ForeignKeyViolation, RaiseException, UniqueViolation
from pydantic.alias_generators import to_camel

from app.errors import ApiError

logger = logging.getLogger("lkbonch")

_RULES = (
    ("students do not receive", "Студенту права не выдаются"),
    ("belongs to the admin panel", "Это право есть только у администратора"),
    ("is not assignable", "Такого права нет"),
    ("only an employee can be assigned", "Преподавателем может быть только сотрудник"),
    ("elective block belongs", "Блок выборных относится к другой группе или семестру"),
    ("applications exist only for electives", "Заявку можно подать только на выборную дисциплину"),
    ("direct chat student", "В личном чате одна сторона должна быть студентом"),
    ("direct chat teacher", "В личном чате вторая сторона должна быть сотрудником"),
    ("this certificate cannot", "Для этой справки такой способ получения не предусмотрен"),
    ("reversal target", "Исходная проводка не найдена"),
    ("a reversal cannot be reversed", "Сторно нельзя сторнировать"),
    ("reversal must repeat", "Сторно должно повторить договор, направление и сумму"),
    ("student profile blocks", "Сначала уберите профиль студента"),
    ("employee profile blocks", "Сначала уберите профиль сотрудника"),
    ("clear permissions", "Сначала снимите права, потом меняйте роль"),
    ("student profile requires", "Профиль студента только у роли «студент»"),
    ("employee profile requires", "Профиль сотрудника только у роли «сотрудник»"),
    ("append-only", "Эту запись нельзя изменить"),
)


def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def _russian(message: str) -> str:
    for needle, text in _RULES:
        if needle in message:
            return text
    return "Операция не проходит правила университета"


def register_handlers(app) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for item in exc.errors():
            parts = [to_camel(str(part)) for part in item.get("loc", ()) if part not in ("body", "query", "path")]
            details.append({"field": ".".join(parts), "message": "Проверьте значение"})
        return _error(422, "validation", "Проверьте поля запроса", details)

    @app.exception_handler(UniqueViolation)
    async def unique_error(_request: Request, exc: UniqueViolation) -> JSONResponse:
        logger.info("unique violation: %s", exc)
        return _error(409, "conflict", "Такая запись уже есть")

    @app.exception_handler(ExclusionViolation)
    async def overlap_error(_request: Request, _exc: ExclusionViolation) -> JSONResponse:
        return _error(422, "overlap", "Семестры не должны пересекаться по датам")

    @app.exception_handler(RaiseException)
    async def rule_error(_request: Request, exc: RaiseException) -> JSONResponse:
        logger.info("database rule: %s", exc)
        return _error(422, "rule_rejected", _russian(str(exc)))

    @app.exception_handler(CheckViolation)
    async def check_error(_request: Request, exc: CheckViolation) -> JSONResponse:
        logger.info("check violation: %s", exc)
        return _error(422, "rule_rejected", "Проверьте значения полей")

    @app.exception_handler(ForeignKeyViolation)
    async def fk_error(_request: Request, exc: ForeignKeyViolation) -> JSONResponse:
        logger.info("foreign key: %s", exc)
        return _error(422, "unknown_reference", "Связанная запись не найдена")

    @app.exception_handler(DbError)
    async def db_error(_request: Request, exc: DbError) -> JSONResponse:
        logger.exception("database error: %s", exc)
        return _error(500, "internal", "Не удалось выполнить операцию")
