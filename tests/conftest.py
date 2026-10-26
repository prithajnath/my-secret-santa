"""
Database fixtures. pytest-postgresql creates a throwaway database for each test on the
PostGIS server in TEST_DATABASE_URL (by default the dev compose's postgres, so run the
tests from inside a dev container). Each test's database is cloned from a template that
already has the extensions and schema, and is dropped when the test finishes.
"""

import os
from urllib.parse import urlparse

import pytest
from pytest_postgresql import factories
from sqlalchemy import URL, create_engine, text

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres@secret-santa-postgres:5432/santa_test",
)
_test_database = urlparse(TEST_DATABASE_URL)

# The app reads DATABASE_URL when it's first imported, so point it at the test database
# before any test module imports it
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def load_schema(host, port, user, dbname, password, **kwargs):
    """Set up the template database: PostGIS plus every model's table."""
    from models import db

    engine = create_engine(
        URL.create(
            "postgresql",
            username=user,
            password=password,
            host=host,
            port=port,
            database=dbname,
        )
    )
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        db.metadata.create_all(connection)
    engine.dispose()


postgresql_noproc = factories.postgresql_noproc(
    host=_test_database.hostname,
    port=_test_database.port or 5432,
    user=_test_database.username,
    password=_test_database.password,
    dbname=_test_database.path.lstrip("/"),
    load=[load_schema],
)
postgresql = factories.postgresql("postgresql_noproc")


@pytest.fixture
def database(postgresql):
    """The app's db, connected to this test's fresh database."""
    from app import app
    from models import db

    with app.app_context():
        yield db
        db.session.remove()
        # Close pooled connections so the test database can be dropped
        db.engine.dispose()
