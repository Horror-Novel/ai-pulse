from app import models
from tests.conftest import login, payload

NW, BP = "Northwind Logistics", "Bluepeak Retail"


def test_employee_export_includes_own_questions_scores_and_report(client):
    headers, _ = login(client, "priya@northwind.test", NW)
    response = client.get("/diagnostic/me/export", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert response.headers["content-disposition"].startswith("attachment;")
    assert data["employee"]["email"] == "priya@northwind.test"
    assert data["organization"]["name"] == NW
    assert data["report"]["status"] == "completed"
    assert data["report"]["scoring_mode"] == "mock"
    assert len(data["responses"]) == data["report"]["answered"]
    assert all(row["question"] and row["answer"] and row["score"] for row in data["responses"])
    assert any(row["ai_explanation"] for row in data["responses"])


def test_delete_is_atomic_and_idempotent_with_no_stale_report(client, db):
    headers, _ = login(client, "priya@northwind.test", NW)
    first = client.delete("/diagnostic/me", headers=headers)
    assert first.status_code == 200 and first.json()["deleted_answers"] > 0
    assert client.delete("/diagnostic/me", headers=headers).json()["deleted_answers"] == 0
    report = client.get("/reports/me", headers=headers).json()
    assert report["status"] == "empty"
    assert report["answered"] == 0 and report["average_score"] is None
    assert report["risks"] == [] and report["next_steps"] == []
    export = client.get("/diagnostic/me/export", headers=headers).json()
    assert export["responses"] == [] and export["report"]["status"] == "empty"
    m = db.query(models.Membership).join(models.User).filter(models.User.email == "priya@northwind.test").one()
    assert db.query(models.Response).filter_by(membership_id=m.id).count() == 0
    assert db.get(models.Assessment, m.id) is None


def test_personal_routes_cannot_target_another_employee(client):
    own, _ = login(client, "priya@northwind.test", NW)
    other, _ = login(client, "arjun@northwind.test", NW)
    before = client.get("/diagnostic/me/export", headers=other).json()["responses"]
    assert client.delete("/diagnostic/me?user_id=6", headers=own).status_code == 400
    assert client.get("/diagnostic/me/export?membership_id=6", headers=own).status_code == 400
    assert client.get("/reports/me?user_id=6", headers=own).status_code == 400
    assert client.delete("/diagnostic/6", headers=own).status_code == 404
    client.delete("/diagnostic/me", headers=own)
    assert client.get("/diagnostic/me/export", headers=other).json()["responses"] == before
    assert client.get("/reports/me", headers=own).json()["name"] == "Priya Nair"


def test_multi_org_export_and_delete_only_selected_organization(client):
    nw, _ = login(client, "ravi@consult.test", NW)
    bp, _ = login(client, "ravi@consult.test", BP)
    for headers in (nw, bp):
        result = client.post("/diagnostic/submit", headers=headers, json=payload(client, headers))
        assert result.status_code == 200, result.text
    original = client.get("/diagnostic/me/export", headers=bp).json()
    assert original["organization"]["name"] == BP
    assert client.delete("/diagnostic/me", headers=nw).status_code == 200
    assert client.get("/diagnostic/me/export", headers=nw).json()["responses"] == []
    assert client.get("/diagnostic/me/export", headers=bp).json()["responses"] == original["responses"]
    assert client.get("/reports/me", headers=bp).json()["status"] == "completed"


def test_legacy_partial_data_is_exportable_but_not_reported_as_complete(client):
    headers, _ = login(client, "vikram@northwind.test", NW)
    export = client.get("/diagnostic/me/export", headers=headers).json()
    assert len(export["responses"]) == 2
    assert export["report"]["status"] == "incomplete"
    assert export["report"]["average_score"] is None
    assert export["report"]["risks"] == []
