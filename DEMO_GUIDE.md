# Five-minute demonstration guide

Use the repository's README setup first. All credentials below are public fixtures for local demonstration only. This guide does not require live AI credentials.

## Start from a reproducible state

PowerShell, from repository root (install dependencies as in README first):

```powershell
Set-Location backend
$env:APP_ENV = "development"
$env:AI_MODE = "mock"
$env:AI_MOCK_SCENARIO = "valid"
# Destructive: use only for this disposable local demo database.
..\.venv\Scripts\python.exe -m app.seed --reset
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Second terminal, from repository root:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open [AI Pulse](http://127.0.0.1:5173). Password for every seeded account: `pulse123`. Keep backend/frontend terminals visible enough to show real requests without exposing environment files or tokens.

## Verified workflows

1. Sign in as `ravi@consult.test`, choose **Bluepeak Retail**: leadership dashboard appears (empty due to privacy). Switch to **Northwind Logistics**: employee diagnostic appears, with no Dashboard navigation. A direct dashboard bypass returns 403; `test_employee_and_multi_org_roles` proves all role/organization combinations.
2. Sign in as `asha@northwind.test` in a separate browser window/context. Choose Northwind. Only **Support** appears, with **5 completed employees**, a score between 1 and 5, and no individual answers. Other groups are absent.
3. Sign in as `priya@northwind.test` in another tab. Choose Northwind, open **My report & data**. Existing report is complete and marked simulated.
4. Click **Export my data (JSON)**. Open the downloaded file. It contains Priya's own answers, question text, scores/explanation and Northwind report; no other employee records.
5. Click **Delete my diagnostic data**, inspect the organization-specific warning, and confirm. The report becomes empty. Export again if desired: `responses: []` and an empty report.
6. Return to Asha's dashboard: on focus/within five seconds (or click **Refresh dashboard**) Support disappears. This proves five-to-four suppression after deletion. No company average or hidden risk total appears.
7. As Priya, take the diagnostic and answer every field; choose any provided options and enter an anonymized work example. Submit. The new report appears; Support reappears at five on the admin dashboard. Retake replaces rather than appends answers.

## Trustworthy AI failure

For a short recording, show the deterministic automated test:

```powershell
# backend/
..\.venv\Scripts\python.exe -m pytest -q tests/test_scoring.py tests/test_diagnostic.py
```

For a visible application failure, stop the backend (Ctrl+C), then restart **without resetting the database**:

```powershell
$env:AI_MOCK_SCENARIO = "invalid"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Sign in again after restarting if using a process-local secret. Retake an existing employee's diagnostic. Submit all answers. Expected: **AI evaluation failed validation; no answers were saved.** The form retains input. The earlier report remains unchanged; a score of 7 is not accepted. Restore `$env:AI_MOCK_SCENARIO = "valid"` and restart before continuing the demo.

Do not describe mock scores as AI understanding of the answer. They are deterministic simulations; validation and failure semantics are what this proves.

## Exact verification commands

```powershell
# backend/
..\.venv\Scripts\python.exe -m pytest -q
# frontend/
npm run build
npx playwright install chromium
npm run test:e2e
```

Expected final checks: 95 backend tests and 3 browser tests pass; the frontend builds. Browser tests use temporary databases and ports 8001/5174; they do not alter the demo on port 8000. Screenshots are generated under `frontend/test-results/`; failures retain Playwright traces.

## Suggested recording sequence (maximum 5 minutes)

| Time | Show and explain |
|---|---|
| 0:00–0:35 | Purpose, stack, local mock mode, brief honest safety limitations. |
| 0:35–1:10 | Ravi switching organizations and receiving different roles; mention backend 403 regression tests. |
| 1:10–1:40 | Asha's dashboard: Support at five; hidden smaller departments and no reconstructable company totals. |
| 1:40–2:20 | Priya's private report and actual JSON download (original feature). |
| 2:20–3:10 | Confirm deletion; empty report/export; Asha refresh shows suppression at four. |
| 3:10–4:10 | Complete retake or show already-run browser test evidence; show malformed AI rejection test and explain rollback. |
| 4:10–5:00 | Passing test/build evidence, README decisions, genuine AI mistake, remaining limitations and client questions. |

Prepare tabs and a populated diagnostic before recording to avoid spending time typing. Do not edit the database or change thresholds to stage a result. The candidate records and submits the video/form separately.
