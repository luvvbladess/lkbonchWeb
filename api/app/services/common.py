import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from psycopg.types.json import Json

from app.errors import ApiError, invalid, not_found
from app.schemas import UniversityPublic, UniversitySettings
from app.util import decimal_str, full_name

logger = logging.getLogger("lkbonch")

ADMIN_PERMISSIONS = (
    "attendance.correct_teacher",
    "electives.review",
    "certificates.review",
    "dorm.review",
    "contracts.manage",
    "scholarships.manage",
    "users.manage",
    "import.run",
    "settings.manage",
    "schedule.manage",
    "audit.read",
    "data.correct",
)


def one(conn, sql: str, params: tuple = ()):
    return conn.execute(sql, params).fetchone()


def many(conn, sql: str, params: tuple = ()):
    return conn.execute(sql, params).fetchall()


def must(row, message: str = "Запись не найдена"):
    if row is None:
        raise not_found(message)
    return row


def load_university(conn):
    return must(one(conn, "SELECT * FROM university WHERE id = 1"), "Университет не настроен")


def enabled_sections(conn) -> list[str]:
    return list(load_university(conn)["enabled_sections"])


def require_section(conn, code: str) -> None:
    if code not in enabled_sections(conn):
        raise ApiError(404, "section_disabled", "Раздел отключён в этом университете")


def require_section_for_student(conn, user, code: str) -> None:
    if user.role == "student":
        require_section(conn, code)


def university_zone(conn) -> ZoneInfo:
    name = load_university(conn)["timezone"]
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def university_today(conn) -> date:
    return datetime.now(university_zone(conn)).date()


def public_university(row) -> UniversityPublic:
    logo = "/api/v1/university/logo" if row["logo_file_id"] else None
    return UniversityPublic(
        name=row["name"],
        short_name=row["short_name"],
        brand_seed=row["brand_seed"],
        brand_accent=row["brand_accent"],
        enabled_sections=list(row["enabled_sections"]),
        logo_url=logo,
    )


def settings_university(row) -> UniversitySettings:
    public = public_university(row)
    return UniversitySettings(
        **public.model_dump(),
        timezone=row["timezone"],
        student_match_field=row["student_match_field"],
        pass_score=decimal_str(row["pass_score"]),
        failing_labels=list(row["failing_labels"]),
    )


def notify(conn, user_id, kind: str, title: str, body: str = "", payload: dict | None = None) -> None:
    conn.execute(
        """
        INSERT INTO notifications (user_id, type, title, body, payload)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, kind, title, body, Json(payload or {})),
    )


def notify_many(conn, user_ids, kind: str, title: str, body: str = "", payload: dict | None = None) -> None:
    seen: set = set()
    for user_id in user_ids:
        if user_id is None or user_id in seen:
            continue
        seen.add(user_id)
        notify(conn, user_id, kind, title, body, payload)


def audit(conn, actor_id, action: str, entity_type: str, entity_id, payload: dict | None = None) -> None:
    conn.execute(
        """
        INSERT INTO audit_events (actor_user_id, action, entity_type, entity_id, payload)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (actor_id, action, entity_type, str(entity_id or ""), Json(payload or {})),
    )


def parse_amount(value: str | None, *, allow_zero: bool = False) -> Decimal:
    if value is None or str(value).strip() == "":
        raise invalid("bad_amount", "Укажите сумму")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise invalid("bad_amount", "Сумма записана не числом") from exc
    amount = amount.quantize(Decimal("0.01"))
    if allow_zero:
        if amount < 0:
            raise invalid("bad_amount", "Сумма не может быть отрицательной")
    elif amount <= 0:
        raise invalid("bad_amount", "Сумма должна быть больше нуля")
    return amount


def parse_score(value: str | None) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).strip()).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise invalid("bad_score", "Балл записан не числом") from exc


def blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def person(row, prefix: str = "") -> str:
    return full_name(
        row[f"{prefix}last_name"],
        row[f"{prefix}first_name"],
        row.get(f"{prefix}middle_name"),
    )


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return 50
    return min(max(limit, 1), 100)
