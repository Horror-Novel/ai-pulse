# Client request (received after the previous developer left)

> **From:** HR team, Northwind Logistics
> **Subject:** AI Pulse pilot: two changes before rollout
>
> Hi team, our legal and HR teams reviewed the AI Pulse pilot and need two changes before we can roll it out:
>
> 1. **No small groups on the dashboard.** If a department has fewer than 5 people who completed the diagnostic, leadership must not see that department's scores or risks on their own. Group them under "Other teams" or hide them, but individuals must never be identifiable.
> 2. **Right to delete.** Any employee must be able to delete all their answers and their report themselves, and it must disappear from every dashboard immediately.
>
> Thanks, Northwind HR

## Implementation status

**Status: Completed and verified** for the tested local pilot scope. Verification performed on **29 October 2026**.

### 1. Small-group privacy

The backend hides any department with fewer than five distinct employees who have completed a valid diagnostic in the relevant organization and department. Partial, duplicate or invalid results do not qualify. Hidden departments contribute no scores or risks to dashboard summaries. Risk summaries also exclude suppressed rare department risk cells, preventing reconstruction by subtraction from published counts.

Implementation: [dashboard.py](backend/app/routes/dashboard.py), [assessments.py](backend/app/services/assessments.py) and [Dashboard.jsx](frontend/src/pages/Dashboard.jsx).

### 2. Employee right to delete

Authenticated employees can confirm deletion of all their diagnostic answers and the corresponding completion/report source in the selected organization. Ownership comes from the authenticated membership; the route accepts no employee identifier. Deletion commits atomically, is safe to repeat, and leaves other employees and organizations untouched. Reports are computed on request, so there is no separate stale stored report. Subsequent dashboard requests immediately recalculate the results and privacy threshold.

Implementation: [diagnostic.py](backend/app/routes/diagnostic.py), [reports.py](backend/app/routes/reports.py), [auth.py](backend/app/auth.py) and [Report.jsx](frontend/src/pages/Report.jsx).

### Verification evidence

- [test_privacy.py](backend/tests/test_privacy.py): four versus five completed employees; partial/corrupt and cross-organization records; distinct employees; suppressed scores/risks and summary reconstruction; deletion-triggered suppression and retake restoration.
- [test_personal_data.py](backend/tests/test_personal_data.py): own-data deletion, idempotency, empty reports/exports, denial of requests targeting another employee, and multi-organization isolation.
- [test_security.py](backend/tests/test_security.py) and [test_api.py](backend/tests/test_api.py): authentication, organization membership, per-organization roles and cross-tenant dashboard denial.
- [test_diagnostic.py](backend/tests/test_diagnostic.py): complete submissions, replacement policy, AI failure preservation and transaction rollback on deletion/submission commit failure.
- [workflows.spec.js](frontend/tests/workflows.spec.js): real browser confirmation, deletion, empty report/export, automatic five-to-four dashboard suppression and restoration after a retake.

Commands executed from the indicated directories:

```powershell
# backend/
..\.venv\Scripts\python.exe -m pytest -q
# frontend/
npm run build
npm run test:e2e
```

Results: **95 backend tests passed**, **production build passed**, **3 browser workflows passed**. The backend emits one upstream Starlette warning about its deprecated HTTPX test transport; it does not cause a test failure. Tests use isolated databases and deterministic mock scoring, with no paid model calls.

### Limitations and client clarification

- Server recalculation is immediate on subsequent requests. Already open dashboards refresh every five seconds, on focus or manually; zero-latency updates across browser sessions are not implemented. Confirm that this refresh behavior meets the client's intended meaning of "immediately."
- Threshold suppression prevents the tested small-group/aggregate disclosures, but does not guarantee anonymity against external knowledge or comparisons across releases. Confirm the required release policy before claiming individuals can never be identified.
- Deletion is per selected organization. Confirm whether the client instead requires deletion across all memberships, and agree retention/deletion policies for backups and external AI providers. Exported files and screenshots cannot be retracted.
- Confirm whether administrator memberships should contribute to department results, and how transfers, question-bank changes and retakes should affect completion.

The [README](README.md) documents the complete assessment status, setup, fixes, original feature, AI usage and remaining production limitations.
