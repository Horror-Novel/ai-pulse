"""Shared completion and mutation rules for personal reports and team analytics."""
import math

from sqlalchemy import update

from .. import models
from .questions import questions_for
from .scoring import Evaluation


def lock_membership(db, membership_id):
    # A harmless write serializes submit/delete for this membership in SQLite;
    # row locking does the same in PostgreSQL. Never hold this lock during AI calls.
    db.execute(update(models.Membership).where(models.Membership.id == membership_id)
               .values(id=models.Membership.id), execution_options={"synchronize_session": False})


def completed_rows(db, membership, rows=None):
    assessment = db.get(models.Assessment, membership.id)
    if assessment is None:
        return []
    questions = {q["id"]: q for q in questions_for(membership.job_role, membership.seniority)}
    rows = rows if rows is not None else db.query(models.Response).filter_by(membership_id=membership.id).all()
    # Fail closed for legacy, duplicate, incomplete, or now-ineligible records.
    if (not questions or len(rows) != len(questions)
            or {r.question_id for r in rows} != set(questions)
            or set(assessment.question_ids) != set(questions)):
        return []
    for row in rows:
        q = questions[row.question_id]
        if row.score is None or not math.isfinite(row.score) or not 1 <= row.score <= 5:
            return []
        if q["type"] == "mcq":
            if not any(o["text"] == row.answer and o["points"] == row.score for o in q["options"]):
                return []
        else:
            try:
                result = Evaluation.model_validate({"score": row.score, "reason": row.reason, "flags": row.flags})
                if not result.reason.strip():
                    return []
            except ValueError:
                return []
    return rows
