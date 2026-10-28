from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership
from ..config import AI_MODE
from ..services.questions import questions_for, load_questions
from ..services.scoring import score_open_answer, ScoringError
from ..services.assessments import lock_membership

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question_id: str = Field(min_length=1, max_length=40)
    answer: str = Field(min_length=1, max_length=5000)


class SubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answers: list[AnswerIn] = Field(min_length=1, max_length=50)


def personal_scope(request: Request):
    # These self-service routes deliberately have no caller-controlled identifiers.
    if request.query_params:
        raise HTTPException(400, "Personal data scope comes from your selected organization; omit query parameters")


@router.get("/questions")
def get_questions(m: models.Membership = Depends(current_membership)):
    return [
        {k: q[k] for k in ("id", "type", "text")} | (
            {"options": [o["text"] for o in q["options"]]} if q["type"] == "mcq" else {}
        ) for q in questions_for(m.job_role, m.seniority)
    ]


@router.post("/submit", dependencies=[Depends(personal_scope)])
def submit(body: SubmitIn, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    bank = {q["id"]: q for q in questions_for(m.job_role, m.seniority)}
    ids = [a.question_id for a in body.answers]
    if len(ids) != len(set(ids)) or set(ids) != set(bank):
        raise HTTPException(400, "Submit every eligible question exactly once")
    # Validate the entire request before spending money or changing persisted data.
    for a in body.answers:
        q = bank[a.question_id]
        if not a.answer.strip():
            raise HTTPException(400, "Answers must not be blank")
        if q["type"] == "mcq" and a.answer not in {o["text"] for o in q["options"]}:
            raise HTTPException(400, f"Invalid option for {q['id']}")
    rows = []
    try:
        for a in body.answers:
            q = bank[a.question_id]
            if q["type"] == "mcq":
                result = {"score": next(o["points"] for o in q["options"] if o["text"] == a.answer), "flags": []}
            else:
                result = score_open_answer(q["text"], a.answer)
            rows.append(models.Response(membership_id=m.id, question_id=q["id"], answer=a.answer, **result))
    except ScoringError as exc:
        db.rollback()
        raise HTTPException(exc.status, str(exc)) from exc
    try:
        lock_membership(db, m.id)
        db.query(models.Response).filter_by(membership_id=m.id).delete(synchronize_session=False)
        assessment = db.get(models.Assessment, m.id)
        if assessment is None:
            assessment = models.Assessment(membership_id=m.id)
            db.add(assessment)
        assessment.question_ids = ids
        assessment.scoring_mode = AI_MODE
        assessment.completed_at = datetime.now(timezone.utc)
        db.add_all(rows)
        db.commit()
    except (IntegrityError, OperationalError) as exc:
        db.rollback()
        raise HTTPException(409, "Diagnostic changed concurrently; please retry") from exc
    return {"saved": len(rows), "status": "completed", "scoring_mode": AI_MODE}


@router.delete("/me", dependencies=[Depends(personal_scope)])
def delete_my_data(m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    try:
        lock_membership(db, m.id)
        deleted = db.query(models.Response).filter_by(membership_id=m.id).delete(synchronize_session=False)
        db.query(models.Assessment).filter_by(membership_id=m.id).delete(synchronize_session=False)
        db.commit()
    except (IntegrityError, OperationalError) as exc:
        db.rollback()
        raise HTTPException(409, "Diagnostic changed concurrently; please retry") from exc
    return {"deleted_answers": deleted, "org_id": m.org_id, "status": "deleted"}


@router.get("/me/export", dependencies=[Depends(personal_scope)])
def export_my_data(m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    from .reports import build_report
    bank = {q["id"]: q for q in load_questions()}
    rows = db.query(models.Response).filter_by(membership_id=m.id).order_by(models.Response.id).all()
    data = {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "organization": {"id": m.org_id, "name": m.org.name},
        "employee": {"name": m.user.name, "email": m.user.email},
        "report": build_report(m, db),
        "responses": [{"question_id": r.question_id, "question": bank.get(r.question_id, {}).get("text"),
                       "answer": r.answer, "score": r.score, "ai_explanation": r.reason,
                       "risks": r.flags or [], "answered_at": r.created_at.isoformat()} for r in rows],
    }
    return JSONResponse(data, headers={"Content-Disposition": 'attachment; filename="ai-pulse-diagnostic.json"'})
