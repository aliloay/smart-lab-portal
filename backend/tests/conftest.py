"""
Test fixtures. Runs against a real PostgreSQL database (smartlab_test), not
SQLite: the schema uses TIMESTAMPTZ and JSON columns whose behaviour differs,
and booking-window comparisons are exactly the thing that must not be tested
against a different engine than production uses.
"""
import os

# NEVER the live database. The fixtures below DROP and recreate every table, so
# the URL is forced to a database whose name ends in "_test" - even inside the
# backend container, where DATABASE_URL points at the live "smartlab" database.
# (2026-10-05: the old setdefault() kept the container's live URL, and running
# the suite in the container wiped the live database three times.)
_live = os.environ.get("DATABASE_URL",
                       "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/smartlab")
_test_url = os.environ.get("TEST_DATABASE_URL") or (_live.rsplit("/", 1)[0] + "/smartlab_test")
if not _test_url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
    raise SystemExit(f"Refusing to run tests: database {_test_url.rsplit('/', 1)[-1]!r} "
                     "does not end in '_test' - the tests drop every table.")
os.environ["DATABASE_URL"] = _test_url
# Everything the test suite writes is, by definition, a software test.
os.environ["DATA_MODE_DEFAULT"] = "SOFTWARE_TEST"
# A device key of the suite's own: never the live one (the container's .env
# holds the production key), and not the published default either.
TEST_DEVICE_KEY = "test-suite-device-key"
os.environ["DEVICE_API_KEY"] = TEST_DEVICE_KEY


def _ensure_test_database(url: str) -> None:
    """Create the _test database on the same server if it does not exist yet."""
    import psycopg
    name = url.rsplit("/", 1)[-1].split("?")[0]
    admin = url.replace("postgresql+psycopg://", "postgresql://").rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as c:
        if c.execute("select 1 from pg_database where datname = %s", (name,)).fetchone() is None:
            c.execute(f'create database "{name}"')


_ensure_test_database(_test_url)

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.models.tables import utcnow  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Device, DeviceType, Lab, RfidCredential, Role,  # noqa: E402
                        User)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(autouse=True)
def _clean(db):
    """Truncate between tests so each one starts from a known empty state."""
    yield
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    db.commit()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def lab(db) -> Lab:
    l = Lab(code="LAB_TEST", name="Test Lab", capacity=5)
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


@pytest.fixture
def other_lab(db) -> Lab:
    l = Lab(code="LAB_OTHER", name="Other Lab", capacity=5)
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


@pytest.fixture
def alice(db) -> User:
    u = User(email="alice@test.edu", full_name="Alice",
             hashed_password=hash_password("Password123"),
             role=Role.STUDENT, auth_subject="USER1",
             fingerprint_enrolled_at=utcnow(), face_enrolled_at=utcnow())
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def bob(db) -> User:
    u = User(email="bob@test.edu", full_name="Bob",
             hashed_password=hash_password("Password123"),
             role=Role.STUDENT, auth_subject="USER2",
             fingerprint_enrolled_at=utcnow(), face_enrolled_at=utcnow())
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def admin(db) -> User:
    u = User(email="admin@test.edu", full_name="Admin",
             hashed_password=hash_password("Password123"), role=Role.ADMIN)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def device(db, lab) -> Device:
    d = Device(device_uid="MASTER_TEST", name="Test Master",
               device_type=DeviceType.MASTER_CONTROLLER, lab_id=lab.id)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@pytest.fixture
def alice_card(db, alice) -> RfidCredential:
    c = RfidCredential(uid_hex="8952FF1F", label="tag", user_id=alice.id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def device_headers():
    return {"X-Device-Key": TEST_DEVICE_KEY}


def auth_headers(client: TestClient, email: str,
                 password: str = "Password123") -> dict:
    r = client.post("/api/auth/login", json={"email": email,
                                             "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def hour():
    return timedelta(hours=1)


@pytest.fixture
def staff(db) -> User:
    u = User(email="staff@test.edu", full_name="Lab Technician",
             hashed_password=hash_password("Password123"),
             role=Role.LAB_STAFF, auth_subject="STAFF1",
             fingerprint_enrolled_at=utcnow(), face_enrolled_at=utcnow())
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path):
    """Issue photos go to a per-test directory, never the real upload dir."""
    from app.services.storage import LocalStorage, set_storage
    store = LocalStorage(str(tmp_path / "uploads"))
    set_storage(store)
    yield store
    set_storage(None)


def image_bytes(fmt: str = "JPEG", size=(640, 480), color=(40, 90, 160),
                exif: bytes | None = None) -> bytes:
    """A real, decodable image in the given format."""
    import io

    from PIL import Image
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    kwargs = {"exif": exif} if exif else {}
    img.save(buf, fmt, **kwargs)
    return buf.getvalue()
