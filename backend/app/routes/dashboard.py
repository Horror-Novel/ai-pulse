"""Only eligible departments contribute to any returned performance aggregate."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership
from ..services.assessments import completed_rows
from ..utils import maturity_level

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
PRIVACY_THRESHOLD = 5


@router.get("")
def org_dashboard(org_id: int, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    if org_id != m.org_id or m.role != "admin":
        raise HTTPException(403, "Admin access to the selected organization is required")

    departments = []
    all_flags = Counter()
    members = db.query(models.Membership).filter_by(org_id=m.org_id, role="employee").all()
    for dept in m.org.departments:
        completed = {}
        for member in members:
            if member.department_id != dept.id:
                continue
            rows = completed_rows(db, member)
            if rows:
                # Distinct employees, even if an inherited DB has duplicate memberships.
                completed[member.user_id] = rows
        if len(completed) < PRIVACY_THRESHOLD:
            continue  # No counts, scores, risk flags, or summary contribution.
        employee_means = [sum(r.score for r in rows) / len(rows) for rows in completed.values()]
        average = sum(employee_means) / len(employee_means)
        flags = Counter()
        for rows in completed.values():
            flags.update({f for r in rows for f in (r.flags or [])})
        # Summaries must aggregate only published cells; otherwise subtracting
        # visible department counts could reconstruct a suppressed rare flag.
        published_flags = {f: n for f, n in flags.items() if n >= PRIVACY_THRESHOLD}
        all_flags.update(published_flags)
        departments.append({
            "department": dept.name,
            "completed_employees": len(completed),
            "average_score": round(average, 2),
            "level": maturity_level(average),
            # Rare flags are also hidden to reduce singling-out risk.
            "risks": sorted(published_flags.items()),
        })
    return {
        "organization": m.org.name,
        "privacy_threshold": PRIVACY_THRESHOLD,
        "privacy_notice": "Only departments with at least 5 completed employees are shown. Hidden departments do not contribute to summaries. Risk labels require at least 5 affected employees.",
        "departments": departments,
        "top_risks": sorted(((f, n) for f, n in all_flags.items() if n >= PRIVACY_THRESHOLD),
                            key=lambda pair: (-pair[1], pair[0]))[:5],
    }
