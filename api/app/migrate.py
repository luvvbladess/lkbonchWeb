import os
import subprocess
from pathlib import Path

import psycopg


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    migrations_dir = Path(os.environ.get("MIGRATIONS_DIR", "/db"))
    scripts = sorted(path for path in migrations_dir.glob("*.sql") if path.is_file())
    if not scripts:
        raise SystemExit(f"В {migrations_dir} нет SQL-файлов")

    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}

    for script in scripts:
        if script.name in applied:
            continue
        # Файл может содержать функции с внутренними точками с запятой,
        # поэтому его выполняет psql целиком в одной транзакции.
        subprocess.run(
            [
                "psql",
                database_url,
                "--set",
                "ON_ERROR_STOP=1",
                "--single-transaction",
                "--file",
                str(script),
            ],
            check=True,
        )
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (script.name,),
            )
        print(f"applied {script.name}")


if __name__ == "__main__":
    main()
