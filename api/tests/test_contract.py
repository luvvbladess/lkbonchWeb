import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.exceptions import RequestValidationError

from app.main import app
from app.schemas import TokenPair
from app.security import access_token, decode_access_token, hash_password, verify_password
from app.services.imports import expand_week_dates
from app.services.rating import score_finals
from app.util import decode_cursor, encode_cursor


def test_rating_formulas():
    finals = [(Decimal("4"), Decimal("2")), (Decimal("2"), Decimal("2"))]
    assert score_finals(finals, {"type": "mean", "of": "final_numeric_grades"}) == Decimal("3")
    assert score_finals(finals, {"type": "sum", "of": "final_numeric_grades"}) == Decimal("6")
    assert score_finals(finals, {"type": "weighted_average", "of": "final_numeric_grades", "weight": "credits"}) == Decimal("3")
    skipped = [(Decimal("5"), Decimal("0")), (Decimal("3"), Decimal("1"))]
    assert score_finals(skipped, {"type": "weighted_average", "of": "final_numeric_grades"}) == Decimal("3")
    assert score_finals([(Decimal("5"), Decimal("0"))], {"type": "weighted_average", "of": "final_numeric_grades"}) is None
    assert score_finals([], {"type": "mean", "of": "final_numeric_grades"}) is None
    assert score_finals(finals, {"type": "mean", "of": "something_else"}) is None


def test_week_expansion_keeps_weekday_and_parity():
    start = date(2026, 9, 1)
    end = date(2026, 9, 30)
    mondays = expand_week_dates(start, end, 1, "all")
    assert mondays
    assert all(day.isoweekday() == 1 and start <= day <= end for day in mondays)
    odd = expand_week_dates(start, end, 1, "odd")
    even = expand_week_dates(start, end, 1, "even")
    assert odd and even
    assert all(day.isocalendar().week % 2 == 1 for day in odd)
    assert all(day.isocalendar().week % 2 == 0 for day in even)
    assert set(odd).isdisjoint(even)
    assert set(odd) | set(even) == set(mondays)


def test_cursor_roundtrip():
    moment = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    entity_id = uuid4()
    restored_moment, restored_id = decode_cursor(encode_cursor(moment, entity_id))
    assert restored_moment == moment
    assert restored_id == str(entity_id)


def test_token_pair_is_camel_case_and_jwt_roundtrips():
    user_id = uuid4()
    token, expires_in = access_token(user_id, "student")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "student"
    assert expires_in == 15 * 60
    pair = TokenPair(access_token=token, refresh_token="refresh", expires_in=expires_in)
    dumped = pair.model_dump(by_alias=True, mode="json")
    assert set(dumped) == {"accessToken", "refreshToken", "expiresIn"}
    password_hash = hash_password("correct horse")
    assert verify_password("correct horse", password_hash)
    assert not verify_password("wrong", password_hash)


def test_validation_error_uses_the_mobile_shape():
    handler = app.exception_handlers[RequestValidationError]
    error = RequestValidationError([{"loc": ("body", "last_name"), "msg": "Field required", "type": "missing"}])
    response = asyncio.run(handler(None, error))
    assert response.status_code == 422
    body = response.body.decode()
    assert '"code":"validation"' in body.replace(" ", "")
    assert "lastName" in body


def test_openapi_is_ready_for_kotlin():
    spec = app.openapi()
    assert spec["openapi"].startswith("3.0")
    operation_ids = []

    def walk(node):
        if isinstance(node, dict):
            if "operationId" in node:
                operation_ids.append(node["operationId"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(spec["paths"])
    assert "login" in operation_ids
    assert "createMessage" in operation_ids
    assert "createDemoPayment" in operation_ids
    assert "listTeachingGrades" in operation_ids
    assert len(operation_ids) == len(set(operation_ids))
    token_pair = spec["components"]["schemas"]["TokenPair"]["properties"]
    assert "accessToken" in token_pair
    assert "refreshToken" in token_pair
    login = spec["paths"]["/api/v1/auth/login"]["post"]
    assert not login.get("security")
    me = spec["paths"]["/api/v1/me"]["get"]
    assert me["security"][0]
    assert "bearer" in spec["components"]["securitySchemes"] or any(
        scheme.get("scheme") == "bearer" for scheme in spec["components"]["securitySchemes"].values()
    )
    grades = spec["paths"]["/api/v1/teaching/{group_discipline_id}/grades"]["get"]
    assert grades["operationId"] == "listTeachingGrades"
