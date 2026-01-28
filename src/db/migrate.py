"""Run database migrations against the configured Postgres database.

Requires DATABASE_URL in .env or .env.local (Postgres connection string from
Supabase Dashboard → Database → Connection string).

Usage:
    uv run python -m src.db.migrate
"""

from pathlib import Path

from dotenv import load_dotenv

# Project root (parent of src/)
_project_root = Path(__file__).resolve().parent.parent.parent
# Load .env and .env.local so DATABASE_URL is available without full app config
load_dotenv(_project_root / ".env")
load_dotenv(_project_root / ".env.local")


def run_migrations() -> None:
    """Apply migration SQL files in migrations/ in order."""
    import os
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit(
            "DATABASE_URL is not set. Add your Postgres connection string to .env or .env.local.\n"
            "Get it from Supabase Dashboard → Project Settings → Database → Connection string (URI)."
        )

    migrations_dir = Path(__file__).resolve().parent.parent.parent / "migrations"
    if not migrations_dir.is_dir():
        raise SystemExit(f"Migrations directory not found: {migrations_dir}")

    # Run in lexicographic order (001_initial.sql, 002_multi_tenant.sql, ...)
    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        raise SystemExit(f"No .sql files found in {migrations_dir}")

    import psycopg
    try:
        with psycopg.connect(database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                for path in sql_files:
                    sql = path.read_text()
                    print(f"Applying {path.name}...")
                    cur.execute(sql)
                    print(f"  OK {path.name}")
    except psycopg.OperationalError as e:
        hint = ""
        err_str = str(e)
        if "No route to host" in err_str or "2600:" in err_str:
            hint = (
                "\n\nIf you used the 'Direct' connection string, your network may not reach Supabase over IPv6. "
                "Use the 'Session' or 'Transaction' pooler connection string instead: "
                "Supabase Dashboard → Project Settings → Database → Connection string → URI (Session or Transaction mode)."
            )
        elif "password authentication failed" in err_str:
            hint = (
                "\n\nCheck: (1) Use the exact URI from Supabase Dashboard → Database → Connection string "
                "(pooler uses username postgres.PROJECT_REF). (2) Use your database password (not the anon/service key). "
                "(3) If the password has # @ % or :, percent-encode it (e.g. # → %23). "
                "(4) Reset the database password in Database settings if needed."
            )
        raise SystemExit(f"Database connection failed: {e}{hint}") from e

    print("Migrations complete.")


if __name__ == "__main__":
    run_migrations()
