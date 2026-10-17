from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_conn
from app.errors import ApiError, forbidden
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    role: str
    status: str
    last_name: str
    first_name: str
    middle_name: str
    login: str | None
    email: str | None
    phone: str | None
    permissions: frozenset[str]

    def require(self, code: str) -> None:
        if code not in self.permissions:
            raise forbidden()


def require_user(
    conn=Depends(get_conn),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if credentials is None:
        raise ApiError(401, "unauthorized", "Войдите снова")
    payload = decode_access_token(credentials.credentials)
    row = conn.execute(
        """
        SELECT u.id, u.role, u.status, u.last_name, u.first_name, u.middle_name,
               u.login, u.email, u.phone,
               COALESCE(
                   array_agg(p.permission_code) FILTER (WHERE p.permission_code IS NOT NULL),
                   '{}'
               ) AS permissions
        FROM users u
        LEFT JOIN user_permissions p ON p.user_id = u.id
        WHERE u.id = %s
        GROUP BY u.id
        """,
        (payload["sub"],),
    ).fetchone()
    if row is None or row["status"] == "blocked":
        raise ApiError(401, "unauthorized", "Войдите снова")
    return CurrentUser(
        id=row["id"],
        role=row["role"],
        status=row["status"],
        last_name=row["last_name"],
        first_name=row["first_name"],
        middle_name=row["middle_name"],
        login=row["login"],
        email=row["email"],
        phone=row["phone"],
        permissions=frozenset(row["permissions"]),
    )
