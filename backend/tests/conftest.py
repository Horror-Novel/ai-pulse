"""Each test gets a separate SQLite file copied from one deterministic demo template."""
import os
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AI_MODE"] = "mock"
os.environ["AI_MOCK_SCENARIO"] = "valid"
os.environ["SECRET_KEY"] = "test-only-signing-secret-at-least-32-characters"

from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app import seed


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("template") / "template.db"
    engine = create_engine(f"sqlite:///{path}")
    original_engine, original_session = seed.engine, seed.SessionLocal
    seed.engine, seed.SessionLocal = engine, sessionmaker(bind=engine)
    try:
        seed.run()
    finally:
        seed.engine, seed.SessionLocal = original_engine, original_session
        engine.dispose()
    return path


@pytest.fixture()
def session_factory(tmp_path, template_db):
    path = tmp_path / "test.db"
    with sqlite3.connect(template_db) as source, sqlite3.connect(path) as target:
        source.backup(target)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture()
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(session_factory):
    def override():
        with session_factory() as session:
            yield session
    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login(client, email, org_name=None):
    r = client.post("/auth/login", json={"email": email, "password": "pulse123"})
    assert r.status_code == 200, r.text
    data = r.json()
    token = data["token"]
    if org_name:
        org = next(o for o in data["organizations"] if o["org_name"] == org_name)
        selected = client.post("/auth/select-org", json={"org_id": org["org_id"]},
                               headers={"Authorization": f"Bearer {token}"})
        assert selected.status_code == 200, selected.text
        token = selected.json()["token"]
    return {"Authorization": f"Bearer {token}"}, data


def payload(client, headers, text="I draft with AI, remove private details and check facts."):
    questions = client.get("/diagnostic/questions", headers=headers).json()
    return {"answers": [{"question_id": q["id"], "answer": q["options"][3] if q["type"] == "mcq" else text}
                        for q in questions]}
