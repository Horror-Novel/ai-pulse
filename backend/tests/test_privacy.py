import pytest
from app import models
from tests.conftest import login, payload
from app.services.questions import questions_for

NW = "Northwind Logistics"


def support_members(db):
    return (db.query(models.Membership).join(models.Department)
            .filter(models.Department.name == "Support", models.Membership.org_id == 1).all())


def dashboard(client):
    headers, _ = login(client, "asha@northwind.test", NW)
    response = client.get("/dashboard?org_id=1", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_five_complete_employees_are_visible(client):
    data = dashboard(client)
    assert len(data["departments"]) == 1
    dept = data["departments"][0]
    assert dept["department"] == "Support"
    assert dept["completed_employees"] == 5
    assert 1 <= dept["average_score"] <= 5
    assert "Sales" not in str(data) and "HR" not in str(data)


def test_four_completed_are_fully_suppressed(client, db):
    m = support_members(db)[0]
    db.query(models.Assessment).filter_by(membership_id=m.id).delete()
    db.commit()
    data = dashboard(client)
    assert data["departments"] == []
    assert data["top_risks"] == []
    assert "average_score" not in data and "completed_employees" not in data


@pytest.mark.parametrize("corruption", ["partial", "unscored", "duplicate", "invalid_score"])
def test_corrupt_or_partial_completion_cannot_qualify(client, db, corruption):
    m = support_members(db)[0]
    rows = db.query(models.Response).filter_by(membership_id=m.id).all()
    if corruption == "partial":
        db.delete(rows[0])
    elif corruption == "unscored":
        rows[0].score = None
    elif corruption == "invalid_score":
        rows[0].score = 7
    else:
        db.add(models.Response(membership_id=m.id, question_id=rows[0].question_id,
                               answer=rows[0].answer, score=rows[0].score))
    db.commit()
    assert dashboard(client)["departments"] == []


def test_cross_org_and_repeated_employee_do_not_count(client, db):
    members = support_members(db)
    removed = members[0]
    db.query(models.Assessment).filter_by(membership_id=removed.id).delete()
    # Malformed inherited cross-tenant department reference must not qualify.
    outsider = db.query(models.Membership).filter_by(org_id=2, job_role="support").one()
    outsider.department_id = members[1].department_id
    donor = members[1]
    duplicate = models.Membership(user_id=donor.user_id, org_id=1, department_id=donor.department_id,
                                  role="employee", job_role=donor.job_role, seniority=donor.seniority)
    db.add(duplicate)
    db.flush()
    for m in (outsider, duplicate):
        qs = questions_for(m.job_role, m.seniority)
        for q in qs:
            db.add(models.Response(membership_id=m.id, question_id=q["id"],
                                  answer=q["options"][3]["text"] if q["type"] == "mcq" else "Example",
                                  score=4, reason="Reviewed example", flags=[]))
        db.add(models.Assessment(membership_id=m.id, question_ids=[q["id"] for q in qs], scoring_mode="mock"))
    db.commit()
    assert dashboard(client)["departments"] == []


def test_correct_equal_employee_weighting_and_risks(client, db):
    members = support_members(db)
    expected = []
    for index, m in enumerate(members):
        rows = db.query(models.Response).filter_by(membership_id=m.id).all()
        for row in rows:
            if row.question_id == "common-open":
                row.score = index + 1
                row.flags = ["policy_unaware"]
        expected.append(sum(r.score for r in rows) / len(rows))
    db.commit()
    data = dashboard(client)
    assert data["departments"][0]["average_score"] == round(sum(expected) / 5, 2)
    assert data["top_risks"] == [["policy_unaware", 5]]
    assert data["departments"][0]["risks"] == [["policy_unaware", 5]]


def test_suppressed_risks_never_enter_summary(client, db):
    # All existing groups except Support are suppressed; add a distinctive flag to Sales.
    m = db.query(models.Membership).join(models.User).filter(models.User.email == "vikram@northwind.test").one()
    row = db.query(models.Response).filter_by(membership_id=m.id, question_id="common-open").one()
    row.flags = ["confidential_data_shared"]
    db.commit()
    assert "confidential_data_shared" not in str(dashboard(client))


def test_summary_cannot_reconstruct_a_suppressed_risk_cell(client, db):
    for m in support_members(db):
        row = db.query(models.Response).filter_by(membership_id=m.id, question_id="common-open").one()
        row.flags = ["policy_unaware"]
    sales = db.query(models.Department).filter_by(org_id=1, name="Sales").one()
    for index in range(5):
        user = models.User(name=f"Fixture {index}", email=f"fixture{index}@test.invalid", password_hash="unused")
        db.add(user)
        db.flush()
        m = models.Membership(user_id=user.id, org_id=1, department_id=sales.id, role="employee",
                              job_role="support", seniority="junior")
        db.add(m)
        db.flush()
        qs = questions_for(m.job_role, m.seniority)
        for q in qs:
            db.add(models.Response(membership_id=m.id, question_id=q["id"],
                answer=q["options"][3]["text"] if q["type"] == "mcq" else "Example",
                score=4, reason="Reviewed example", flags=["policy_unaware"] if index == 0 and q["type"] == "open" else []))
        db.add(models.Assessment(membership_id=m.id, question_ids=[q["id"] for q in qs], scoring_mode="mock"))
    db.commit()
    data = dashboard(client)
    assert len(data["departments"]) == 2
    assert next(d for d in data["departments"] if d["department"] == "Sales")["risks"] == []
    # Six would reveal the suppressed single employee by subtracting Support's five.
    assert data["top_risks"] == [["policy_unaware", 5]]


def test_delete_updates_threshold_immediately_and_retake_restores(client):
    employee, _ = login(client, "priya@northwind.test", NW)
    assert dashboard(client)["departments"][0]["completed_employees"] == 5
    assert client.delete("/diagnostic/me", headers=employee).status_code == 200
    assert dashboard(client)["departments"] == []
    assert dashboard(client)["top_risks"] == []
    assert client.post("/diagnostic/submit", headers=employee, json=payload(client, employee)).status_code == 200
    assert dashboard(client)["departments"][0]["completed_employees"] == 5
