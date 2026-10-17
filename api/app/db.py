from collections.abc import Iterator

from fastapi import Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

_pool: ConnectionPool | None = None


def open_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def commit_side_effect(sql: str, params: tuple = ()) -> None:
    """Запись, которая должна сохраниться, даже если основной запрос вернёт ошибку."""
    with open_pool().connection() as conn:
        conn.execute(sql, params)
        conn.commit()


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_conn(request: Request) -> Iterator[object]:
    pool: ConnectionPool = request.app.state.pool
    with pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
