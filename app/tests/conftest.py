import unittest.mock
import mongomock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_fake_client = mongomock.MongoClient()

def _get_db():
    return _fake_client.main

@pytest.fixture(autouse=True)
def reset_db():
    db = _fake_client.main
    for collection_name in db.list_collection_names():
        db[collection_name].drop()
    yield

class DummySession:
    def __bool__(self): return False
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def start_transaction(self): pass
    def commit_transaction(self): pass
    def abort_transaction(self): pass

class DummyClient:
    def start_session(self): return DummySession()

class SMTPDummySession:
    def __init__(self, *args): pass
    def __enter__(self): return unittest.mock.Mock()
    def __exit__(self, *args): pass

def _make_bucket_mock():
    fake_blob = unittest.mock.Mock()
    with open('tests/resources/sellefrançais.jpg', 'rb') as f:
        fake_blob.download_as_string.return_value = f.read()
    fake_blob.content_type = 'image/jpg'
    bucket = unittest.mock.Mock()
    bucket.blob.return_value = fake_blob
    return bucket

@pytest.fixture
def fake_db():
    return _get_db()

@pytest.fixture
def auth_client():
    from app.routers.auth import router as auth_router
    app = FastAPI()
    app.dependency_overrides[auth_router.get_db] = _get_db
    app.dependency_overrides[auth_router.get_db_client] = lambda: DummyClient()
    auth_router.mailing_utils.smtplib.SMTP = SMTPDummySession
    auth_router.monitoring_tools.send_telegram_message = unittest.mock.Mock()
    app.include_router(auth_router.router)
    return TestClient(app)

@pytest.fixture
def stallions_client():
    from app.routers.stallions import router as stallions_router
    app = FastAPI()
    app.dependency_overrides[stallions_router.get_db] = _get_db
    app.dependency_overrides[stallions_router.get_db_client] = lambda: DummyClient()
    app.dependency_overrides[stallions_router.get_stalllion_photos_bucket] = lambda: _make_bucket_mock()
    stallions_router.monitoring_tools.send_telegram_message = unittest.mock.AsyncMock()
    app.include_router(stallions_router.router)
    return TestClient(app)

@pytest.fixture
def covers_client():
    from app.routers.covers import router as covers_router
    app = FastAPI()
    app.dependency_overrides[covers_router.get_db] = _get_db
    app.include_router(covers_router.router)
    return TestClient(app)

@pytest.fixture
def payments_client():
    from app.routers.payments import router as payments_router
    app = FastAPI()
    app.dependency_overrides[payments_router.get_db] = _get_db
    app.dependency_overrides[payments_router.get_db_client] = lambda: DummyClient()
    app.include_router(payments_router.router)
    return TestClient(app)

@pytest.fixture
def contracts_client():
    from app.routers.contracts import router as contracts_router
    app = FastAPI()
    app.dependency_overrides[contracts_router.get_db] = _get_db
    app.dependency_overrides[contracts_router.get_db_client] = lambda: DummyClient()
    contracts_router.monitoring_tools.send_telegram_message = unittest.mock.AsyncMock()
    app.include_router(contracts_router.router)
    return TestClient(app)

@pytest.fixture
def users_client():
    from app.routers.users import router as users_router
    app = FastAPI()
    app.dependency_overrides[users_router.get_db] = _get_db
    app.dependency_overrides[users_router.get_db_client] = lambda: DummyClient()
    app.include_router(users_router.router)
    return TestClient(app)

@pytest.fixture
def mailing_client():
    from app.routers.mailing import router as mailing_router
    app = FastAPI()
    app.dependency_overrides[mailing_router.get_db] = _get_db
    app.dependency_overrides[mailing_router.get_db_client] = lambda: DummyClient()
    app.include_router(mailing_router.router)
    return TestClient(app)

@pytest.fixture
def admin_client():
    from app.routers.admin import router as admin_router
    app = FastAPI()
    app.dependency_overrides[admin_router.get_db] = _get_db
    app.include_router(admin_router.router)
    return TestClient(app)

@pytest.fixture
def stallion_owners_client():
    from app.routers.stallion_owners import router as stallion_owners_router
    app = FastAPI()
    app.dependency_overrides[stallion_owners_router.get_db] = _get_db
    app.include_router(stallion_owners_router.router)
    return TestClient(app)

@pytest.fixture
def geoloc_client():
    from app.routers.geoloc import router as geoloc_router
    app = FastAPI()
    app.include_router(geoloc_router.router)
    return TestClient(app)