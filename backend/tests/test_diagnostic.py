import copy
import pytest
from app import models
from app.services.scoring import ScoringError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from tests.conftest import login, payload


@pytest.mark.parametrize("change", ["missing", "duplicate", "wrong_role", "unknown", "invalid_option", "blank", "wrong_type", "oversized", "extra"])
def test_invalid_submission_does_not_modify_existing_assessment(client, change):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    before = client.get("/diagnostic/me/export", headers=headers).json()["responses"]
    body = payload(client, headers)
    if change == "missing":
        body["answers"].pop()
    elif change == "duplicate":
        body["answers"].append(copy.deepcopy(body["answers"][0]))
    elif change == "wrong_role":
        body["answers"][-1]["question_id"] = "eng-arch"
    elif change == "unknown":
        body["answers"][-1]["question_id"] = "nonexistent"
    elif change == "invalid_option":
        body["answers"][0]["answer"] = "Invented option"
    elif change == "blank":
        body["answers"][0]["answer"] = "   "
    elif change == "wrong_type":
        body["answers"][0]["answer"] = 4
    elif change == "oversized":
        body["answers"][0]["answer"] = "x" * 5001
    else:
        body["membership_id"] = 1
    assert client.post("/diagnostic/submit", headers=headers, json=body).status_code in {400, 422}
    assert client.get("/diagnostic/me/export", headers=headers).json()["responses"] == before


def test_repeated_submission_replaces_without_inflating_data(client, db):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    body = payload(client, headers)
    for _ in range(2):
        response = client.post("/diagnostic/submit", headers=headers, json=body)
        assert response.status_code == 200, response.text
    report = client.get("/reports/me", headers=headers).json()
    assert report["answered"] == len(body["answers"])
    assert report["status"] == "completed"
    m = db.query(models.Membership).join(models.User).filter(models.User.email == "priya@northwind.test").one()
    assert db.query(models.Response).filter_by(membership_id=m.id).count() == len(body["answers"])
    assert db.query(models.Assessment).filter_by(membership_id=m.id).count() == 1


def test_ai_failure_preserves_previous_report_and_answers(client, monkeypatch):
    headers, _ = login(client, "ravi@consult.test", "Northwind Logistics")
    body = payload(client, headers)
    assert client.post("/diagnostic/submit", headers=headers, json=body).status_code == 200
    before = client.get("/diagnostic/me/export", headers=headers).json()
    calls = []
    def failure_on_second(question, answer):
        calls.append(question)
        if len(calls) == 2:
            raise ScoringError()
        return {"score": 4, "reason": "Valid", "flags": []}
    monkeypatch.setattr("app.routes.diagnostic.score_open_answer", failure_on_second)
    assert client.post("/diagnostic/submit", headers=headers, json=body).status_code == 502
    after = client.get("/diagnostic/me/export", headers=headers).json()
    assert len(calls) == 2
    assert after["responses"] == before["responses"]
    assert after["report"] == before["report"]


def test_failed_initial_evaluation_never_creates_success(client, monkeypatch):
    headers, _ = login(client, "dev@northwind.test", "Northwind Logistics")
    monkeypatch.setenv("AI_MOCK_SCENARIO", "invalid")
    result = client.post("/diagnostic/submit", headers=headers, json=payload(client, headers))
    assert result.status_code == 502
    assert client.get("/reports/me", headers=headers).json()["status"] == "empty"


@pytest.mark.parametrize("operation", ["delete", "submit"])
def test_commit_failure_rolls_back_whole_mutation(client, monkeypatch, operation):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    before = client.get("/diagnostic/me/export", headers=headers).json()
    body = payload(client, headers)
    def fail_commit(self):
        raise OperationalError("Simulated database conflict", {}, Exception("test"))
    monkeypatch.setattr(Session, "commit", fail_commit)
    response = (client.delete("/diagnostic/me", headers=headers) if operation == "delete"
                else client.post("/diagnostic/submit", headers=headers, json=body))
    assert response.status_code == 409
    after = client.get("/diagnostic/me/export", headers=headers).json()
    assert before["responses"] == after["responses"]
    assert before["report"] == after["report"]
