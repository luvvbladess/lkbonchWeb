import logging
from datetime import UTC, datetime, timedelta

from psycopg.errors import UniqueViolation

from app.config import settings
from app.db import commit_side_effect
from app.errors import ApiError, invalid
from app.schemas import ACTIVATION_MESSAGE, Ack, TokenPair
from app.security import (
    access_token,
    hash_password,
    hash_token,
    new_activation_code,
    new_refresh_token,
    verify_password,
)
from app.services.common import ADMIN_PERMISSIONS, load_university, one

logger = logging.getLogger("lkbonch")


def _match_field(conn) -> str:
    field = load_university(conn)["student_match_field"]
    if field not in ("student_card_number", "record_book_number"):
        raise invalid("university_settings", "Некорректная настройка идентификации")
    return field


def issue_tokens(conn, user_id, role: str) -> TokenPair:
    token, expires_in = access_token(user_id, role)
    raw = new_refresh_token()
    conn.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES (%s, %s, %s)
        """,
        (user_id, hash_token(raw), datetime.now(UTC) + timedelta(days=settings.refresh_token_days)),
    )
    return TokenPair(access_token=token, refresh_token=raw, expires_in=expires_in)


def request_activation(conn, body) -> Ack:
    identifier = body.identifier.strip()
    if not identifier or not body.last_name.strip() or not body.first_name.strip():
        raise invalid("activation_incomplete", "Укажите фамилию, имя и номер")
    field = _match_field(conn)
    row = one(
        conn,
        f"""
        SELECT u.id, u.status, u.email, u.phone
        FROM users u
        JOIN student_profiles sp ON sp.user_id = u.id
        WHERE u.role = 'student'
          AND u.name_key = person_name_key(%s, %s, %s)
          AND sp.{field} = %s
        """,
        (body.last_name.strip(), body.first_name.strip(), body.middle_name.strip(), identifier),
    )
    destination = None
    if row is not None and row["status"] == "pending":
        destination = row["email"] or row["phone"]
    if destination:
        code = new_activation_code()
        conn.execute(
            """
            UPDATE activation_codes
            SET used_at = now()
            WHERE user_id = %s AND used_at IS NULL
            """,
            (row["id"],),
        )
        conn.execute(
            """
            INSERT INTO activation_codes (user_id, code_hash, destination, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (
                row["id"],
                hash_token(code),
                destination,
                datetime.now(UTC) + timedelta(minutes=15),
            ),
        )
        if settings.expose_activation_codes:
            logger.warning("activation code for %s: %s", destination, code)
    return Ack(message=ACTIVATION_MESSAGE)


def confirm_activation(conn, body) -> TokenPair:
    identifier = body.identifier.strip()
    login = body.login.strip()
    if len(body.password) < 8:
        raise invalid("weak_password", "Пароль должен быть не короче 8 символов")
    if not login:
        raise invalid("login_required", "Укажите логин")
    field = _match_field(conn)
    user = one(
        conn,
        f"""
        SELECT u.id, u.role, u.status
        FROM users u
        JOIN student_profiles sp ON sp.user_id = u.id
        WHERE u.role = 'student'
          AND u.status = 'pending'
          AND u.name_key = person_name_key(%s, %s, %s)
          AND sp.{field} = %s
        """,
        (body.last_name.strip(), body.first_name.strip(), body.middle_name.strip(), identifier),
    )
    code = one(
        conn,
        """
        SELECT id, code_hash, attempts, expires_at
        FROM activation_codes
        WHERE user_id = %s AND used_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],) if user else (None,),
    )
    rejected = (
        user is None
        or code is None
        or code["attempts"] >= 5
        or code["expires_at"] <= datetime.now(UTC)
        or code["code_hash"] != hash_token(body.code.strip())
    )
    if rejected:
        if user is not None and code is not None and code["attempts"] < 5 and code["code_hash"] != hash_token(body.code.strip()):
            commit_side_effect(
                "UPDATE activation_codes SET attempts = attempts + 1 WHERE id = %s",
                (code["id"],),
            )
        raise invalid("code_rejected", "Код не подошёл")
    try:
        with conn.transaction():
            conn.execute(
                """
                UPDATE users
                SET login = %s, password_hash = %s, status = 'active'
                WHERE id = %s
                """,
                (login, hash_password(body.password), user["id"]),
            )
            conn.execute(
                "UPDATE activation_codes SET used_at = now() WHERE id = %s",
                (code["id"],),
            )
    except UniqueViolation as exc:
        raise invalid("login_taken", "Этот логин уже занят") from exc
    return issue_tokens(conn, user["id"], user["role"])


def login(conn, body) -> TokenPair:
    key = body.login.strip()
    rows = conn.execute(
        """
        SELECT id, role, status, password_hash
        FROM users
        WHERE login = %s OR email = %s OR phone = %s
        """,
        (key, key, key),
    ).fetchall()
    if len(rows) != 1 or not rows[0]["password_hash"] or not verify_password(body.password, rows[0]["password_hash"]):
        raise ApiError(401, "unauthorized", "Неверный логин или пароль")
    user = rows[0]
    if user["status"] == "blocked":
        raise ApiError(401, "unauthorized", "Учётная запись заблокирована")
    if user["status"] != "active":
        raise ApiError(401, "unauthorized", "Неверный логин или пароль")
    return issue_tokens(conn, user["id"], user["role"])


def refresh_session(conn, raw_token: str) -> TokenPair:
    row = one(
        conn,
        """
        SELECT t.id, t.user_id, t.expires_at, t.revoked_at, u.role, u.status
        FROM refresh_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token_hash = %s
        """,
        (hash_token(raw_token),),
    )
    if row is None:
        raise ApiError(401, "unauthorized", "Войдите снова")
    if row["revoked_at"] is not None:
        commit_side_effect(
            """
            UPDATE refresh_tokens
            SET revoked_at = now()
            WHERE user_id = %s AND revoked_at IS NULL
            """,
            (row["user_id"],),
        )
        raise ApiError(401, "refresh_reused", "Сессия сброшена. Войдите снова.")
    if row["expires_at"] <= datetime.now(UTC) or row["status"] != "active":
        raise ApiError(401, "unauthorized", "Войдите снова")
    pair = issue_tokens(conn, row["user_id"], row["role"])
    fresh = one(
        conn,
        "SELECT id FROM refresh_tokens WHERE token_hash = %s",
        (hash_token(pair.refresh_token),),
    )
    conn.execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = now(), replaced_by = %s
        WHERE id = %s
        """,
        (fresh["id"], row["id"]),
    )
    return pair


def logout(conn, user_id, raw_token: str) -> None:
    conn.execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = now()
        WHERE token_hash = %s AND user_id = %s AND revoked_at IS NULL
        """,
        (hash_token(raw_token), user_id),
    )


def change_password(conn, user, current: str, new_password: str) -> None:
    if len(new_password) < 8:
        raise invalid("weak_password", "Пароль должен быть не короче 8 символов")
    row = one(conn, "SELECT password_hash FROM users WHERE id = %s", (user.id,))
    if row is None or not row["password_hash"] or not verify_password(current, row["password_hash"]):
        raise invalid("password_rejected", "Текущий пароль не подошёл")
    conn.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (hash_password(new_password), user.id),
    )
    conn.execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = now()
        WHERE user_id = %s AND revoked_at IS NULL
        """,
        (user.id,),
    )


def ensure_bootstrap_admin(conn) -> None:
    login_name = settings.bootstrap_admin_login.strip()
    password = settings.bootstrap_admin_password
    if not login_name or not password:
        return
    if one(conn, "SELECT 1 FROM users WHERE role = 'admin'"):
        return
    row = conn.execute(
        """
        INSERT INTO users (role, status, last_name, first_name, login, password_hash)
        VALUES ('admin', 'active', 'Администратор', 'Системы', %s, %s)
        RETURNING id
        """,
        (login_name, hash_password(password)),
    ).fetchone()
    for code in ADMIN_PERMISSIONS:
        conn.execute(
            "INSERT INTO user_permissions (user_id, permission_code) VALUES (%s, %s)",
            (row["id"], code),
        )
