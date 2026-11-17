"""Start an isolated API for the Playwright end-to-end tests.

It uses its own database (`<db>_e2e`, dropped and migrated on every start), its own Redis DB and its
own port, so the tests can never touch development data. Run from the backend directory.
"""

import os
import subprocess
import sys
from pathlib import Path

# Running a file puts its own folder on the path, not the backend package root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg  # noqa: E402
import redis  # noqa: E402
import uvicorn  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import Settings  # noqa: E402

PORT = 8100
WEB_ORIGIN = "http://localhost:5174"
REDIS_DB = 13

base = Settings()
url = make_url(base.database_url)
db_name = f"{url.database}_e2e"
assert db_name.endswith("_e2e")  # never drop a real database

admin_url = url.set(database="postgres", drivername="postgresql").render_as_string(
    hide_password=False
)
with psycopg.connect(admin_url, autocommit=True) as conn:
    conn.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
    conn.execute(f'CREATE DATABASE "{db_name}"')

redis_url = base.redis_url.rsplit("/", 1)[0] + f"/{REDIS_DB}"
os.environ.update(
    DATABASE_URL=url.set(database=db_name).render_as_string(hide_password=False),
    REDIS_URL=redis_url,
    CORS_ORIGINS=f'["{WEB_ORIGIN}"]',
    AUTH_RATE_LIMIT_PER_MINUTE="100000",
    GAME_API_RATE_LIMIT_PER_MINUTE="100000",
    APP_ENV="test",
    LOG_LEVEL="WARNING",
)
redis.Redis.from_url(redis_url).flushdb()
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"], check=True, capture_output=True
)

uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")
