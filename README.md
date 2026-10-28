# AI Pulse

AI Pulse is a role-adaptive AI usage diagnostic with private employee reports and organization-scoped leadership insights. This assessment keeps the inherited FastAPI / SQLAlchemy / SQLite backend and React / Vite frontend. It is ready for a reproducible **local demonstration**, with the production limitations below.

## Running locally

Use **Python 3.13** and **Node.js 22.12+** (Node 22 LTS recommended). Vite's [Node requirements](https://vite.dev/guide/) changed with the tooling security upgrade. No paid model or external database is needed.

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
Set-Location backend
..\.venv\Scripts\python.exe -m app.seed
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open [the app](http://127.0.0.1:5173). [API documentation](http://127.0.0.1:8000/docs) and [health](http://127.0.0.1:8000/health) are available. Seeding an existing database deliberately refuses to overwrite it. **For a disposable demo database only**, use `python -m app.seed --reset` to erase and recreate the fixtures.

On macOS/Linux, use `python3 -m venv .venv`, `.venv/bin/python` from the root and `../.venv/bin/python` inside backend; use `cp backend/.env.example backend/.env` only if that file does not already exist. Other commands are the same.

### Configuration

Copy `backend/.env.example`; actual `.env` files are ignored. Environment variables take precedence. The simple loader accepts unquoted `NAME=value` lines.

| Variable | Behavior |
|---|---|
| `DATABASE_URL` | Defaults to `sqlite:///./aipulse.db`, relative to the backend working directory. |
| `APP_ENV` | `development` by default. Any other value requires a signing secret of 32+ characters. |
| `SECRET_KEY` | Blank/weak development values use a random process-local key. Restart/reload invalidates tokens; sign in again. For multiple workers, set a stable random secret. |
| `AI_MODE` | `mock` by default; `live` requires HTTPS `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`. Live mode sends open answers to that provider. |
| `AI_MOCK_SCENARIO` | `valid` gives deterministic simulated scores; `invalid` deliberately returns an out-of-range fixture to demonstrate safe failure. |
| `CORS_ORIGINS` | Comma-separated frontend origins; defaults to localhost/127.0.0.1 port 5173. |
| `VITE_API_URL` | Optional frontend build/dev variable; defaults to `http://localhost:8000`. |

Generate a stable local secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep it private. Rotate any secret previously distributed with the inherited repository; history is intentionally preserved. The tracked inherited `.env` was replaced by an example and the local signing key was rotated.

### Demo accounts

All are deliberately public **local fixtures** with password `pulse123`. Never seed a client database.

| Account | Access |
|---|---|
| `asha@northwind.test` | Northwind administrator |
| `meera@bluepeak.test` | Bluepeak administrator |
| `ravi@consult.test` | Northwind employee; Bluepeak administrator |
| `priya@northwind.test` | Support employee, complete diagnostic |
| `arjun@northwind.test`, `kavitha@northwind.test`, `anita@northwind.test`, `nikhil@northwind.test` | Other four completed Support employees |
| `dev@northwind.test` | Lead engineer; demonstrates senior questions |

The seed has exactly five complete Support employees. Sales, Engineering, HR and Bluepeak groups are below threshold. Some original partial records remain to demonstrate that partial data does not qualify.

## What I found wrong

| Priority | Confirmed inherited defect | Impact |
|---|---|---|
| P0 | Dashboard checked the token's admin role, then queried an unrelated caller-supplied organization ID. | Cross-organization leadership data exposure. |
| P1 | Organization selection issued a token without verifying membership. | Invalid organization contexts could be issued; downstream checks were inconsistent. |
| P1 | No small-group suppression, and any answer counted as completion. | Small departments' scores and flags appeared in leadership output. |
| P1 | No self-service deletion. | Client requirement absent. |
| P1 | Submission accepted any bank question, partial sets and duplicates, appending each attempt. | Ineligible answers and repeated attempts inflated analytics. |
| P1 | Seniority used alphabetic string comparison. | Lead managers missed senior questions; reproduced by a failing inherited test. |
| P1 | Department sums were divided by employee count rather than averaged per employee; maturity cutoffs differed from reports. | Misleading scores, potentially exceeding the five-point scale. |
| P2 | Unvalidated model JSON supplied scores, explanations and arbitrary flags. | Invalid scores and malformed replies could become results or server errors. |
| P2 | Unsalted SHA-256 passwords and a known fallback JWT key. | Weak credential protection and forgeable default tokens. |
| P2 | Tests reseeded a fixed database; a purported cross-org test queried the same organization. | Misleading safety evidence and fragile isolation. |
| P2/P3 | Vulnerable dependency versions, tracked environment file, broken Docker import path, missing frontend errors/navigation. | Unsafe tooling and unreliable reproduction. |

## What I fixed

- Centralized JWT/membership checks, verified organization selection, and required the dashboard's requested organization to match the selected membership's admin role. Roles are read from the database on every request.
- Added salted PBKDF2-HMAC-SHA256 at 600,000 iterations and constant-time verification; successful legacy logins upgrade their hashes. The work factor follows [OWASP guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html). No new authentication framework.
- Added one explicit current `Assessment` per membership. Full question eligibility, uniqueness, MCQ options, bounded strings and AI outputs are validated before writes.
- A successful retake atomically replaces the previous set. Failed validation, model calls or database commits preserve the previous assessment. A harmless membership-row update serializes mutations; database conflicts return 409.
- Reports and dashboards use `completed_rows` to reject missing, duplicated, ineligible, unscored or invalid rows. Legacy rows without a completion record remain incomplete.
- Used equal weighting of complete employees' question averages and one shared maturity function. Scores describe this self-report instrument, not a validated performance measure.
- Added bounded provider timeouts, no automatic retries, strict output schema, supported risk labels, complete JSON-fence parsing and duplicate-field rejection. Prompt instructions are separated from untrusted employee answers.
- Improved UI navigation, form validation, error/retry states, deletion confirmation, empty reports, simulated-score notices and a readable dashboard. Tokens are tab-scoped in session storage; private HTTP responses use `no-store`.
- Updated affected dependencies, added resolved locks and CI, isolated test databases, guarded destructive demo resets and repaired the Docker module entry point.

## Client request

### Small-group privacy

Implemented server-side in `backend/app/routes/dashboard.py`. A department needs **five distinct employees with a complete validated diagnostic in that organization and department**. Administrator-only memberships do not contribute.

Below threshold, the entire department entry is absent: no name, completion count, score, maturity or risk field. Hidden departments contribute to **no** organization-wide score or risk total. There is no "Other teams" bucket and no company-wide score to subtract from visible departments. Departments with zero completions are also hidden.

Risks are counted once per employee, not per response. Department risk labels require five affected employees. Organization risk summaries sum only published department risk counts; suppressed rare risk cells never contribute to a summary. Small suppressed cohorts cannot be reconstructed by subtracting displayed company totals because those totals are not supplied.

This is threshold suppression, **not a mathematical anonymity guarantee**. Comparing snapshots of a still-eligible group before/after one employee changes an answer, or knowing other employees' answers, can still reveal information. Formal protection against longitudinal differencing needs a client decision about release intervals, minimum cohort changes or differential privacy.

### Employee-controlled deletion

`DELETE /diagnostic/me` removes all answer rows and the current completion/report source for the authenticated membership in one transaction. Reports are computed on request; there is no stored report/cache to retain. Repeating deletion succeeds with zero deleted answers. Every later dashboard query recalculates eligibility immediately.

The UI confirms the selected organization's name and consequences. It clears the private report after success and supports errors and empty states. Open leadership screens poll every five seconds, on focus, and by manual refresh; they do not receive a zero-latency push. Already downloaded files/screenshots cannot be retracted.

Deletion is **per selected organization**. Employees with several organizations repeat it in each one; other memberships and the account remain intact. Routes accept no employee ID and reject personal-route query parameters. Deletion does not promise removal from provider records, backups, access logs, or exported files.

### Questions for the client

- Is deletion intended for the selected organization or all memberships at once? What retention/backup/provider deletion policy applies?
- Should administrators who also work in a department contribute as employees? How should transfers and role/question-bank changes affect prior completion?
- Are risk-label suppression and hiding whole departments acceptable? What privacy release policy is needed to prevent comparisons over time?
- Who may review/contest model feedback? What provider, consent, region, retention and AI validation requirements apply?
- Should retakes replace the previous assessment (implemented), be restricted by period, or keep a separately governed history?

## Original feature: Employee Diagnostic Data Export

Confirmed absent in the inherited code. `GET /diagnostic/me/export` and **My report & data â†’ Export my data (JSON)** provide organization-specific self-service transparency. The download includes the employee's own question text, answers, per-answer scores, AI explanations/flags, timestamps, scoring mode and personal report. It does not contain passwords, tokens, or other employees' data.

Empty/deleted data exports as an empty response list with an empty report. Incomplete inherited rows can be exported for inspection but are clearly not a completed report; their raw legacy scores are unverified. This single original feature complements the client's control/privacy requests.

## Tests and verification

Baseline: **7 passed, 1 failed** (`test_lead_manager_gets_policy_questions`). The inherited frontend build passed after installing dependencies.

Commands from the indicated directories:

```powershell
# backend/
..\.venv\Scripts\python.exe -m pytest -q

# frontend/
npm ci
npm run build
npx playwright install chromium
npm run test:e2e

# repository root; optional audit tooling
.\.venv\Scripts\python.exe -m pip install pip-audit
.\.venv\Scripts\python.exe -m pip_audit -r backend/requirements.lock
# frontend/
npm audit
```

Browser tests launch real FastAPI and Vite servers on **8001 and 5174**, with a disposable temporary database; they never reset the local demo database. The virtual environment must be named `.venv` in the repository root, or set `PYTHON` to its executable before running Playwright. On a Linux CI host install browser OS packages with `npx playwright install --with-deps chromium`.

Observed on Windows / Python 3.13 / Node 25.2.1:

- Backend: **95 passed**. One upstream Starlette warning deprecates its current HTTPX test transport; tests still pass.
- Browser: **3 passed**, including a real JSON download, submit/report, confirmation cancellation, delete/empty export, automatic five-to-four dashboard suppression, retake restoration, organization switching, direct API denial, and a simulated provider-error UI/retry.
- Frontend: production build passed.
- Backend and frontend audits: no known vulnerabilities in the final resolved dependency sets at verification time. This is not proof that packages are vulnerability-free.
- Provider tests use mocks only: original malformed fixtures, missing fields, types/ranges/flags, timeouts, network/HTTP errors, credentials and prompt message separation.
- The browser error test injects HTTP 502 to exercise the UI; backend tests independently verify actual scoring failure and rollback.
- Dockerfile corrected, but image execution unverified: Docker Desktop's Linux daemon is unavailable here.
- GitHub Actions is configured in `.github/workflows/ci.yml`; remote execution status is reported separately after push.

See [DEMO_GUIDE.md](DEMO_GUIDE.md) and [INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md).

## AI usage

OpenAI Codex inspected the inherited source, proposed and implemented fixes, wrote regression/browser tests, ran tools and reviewed the result. Model calls in verification were deterministic mocks; no paid live LLM request was made. The candidate must personally study, explain and be able to modify this work; AI assistance is disclosed rather than represented as unaided work.

**A genuine AI mistake:** while optimizing test setup, Codex initially computed one salted password hash and reused it for all seeded accounts. Review caught that this defeated individual salts even though ordinary password verification passed. Seeding now hashes each account separately, and `test_seeded_passwords_have_individual_salts` checks distinct hashes. Test setup instead gains speed by copying one template database into isolated per-test databases.

## Tradeoffs and limitations

- Not production-certified. SSO/MFA, password recovery, login/scoring rate limits, session revocation/logout tokens, centralized audit logging, encryption/backup operations and deployment hardening remain unfinished. Browser tokens remain accessible to same-origin scripts; session storage reduces persistence, not XSS risk.
- Schema setup adds the new assessment table without rewriting legacy responses. No full migration framework, historical assessment retention or administrative membership-management API was added. Existing partial answers need a retake; verify a migration/backfill policy before using a real database.
- SQLite is appropriate for this local pilot. Mutation locks/rollback are exercised, but high concurrency, PostgreSQL, load and production infrastructure were not tested. Dashboard queries favor clarity over large-company query efficiency.
- Historical deletion and formal statistical privacy require policy decisions. No claim of provider/backup erasure or full anonymization is made.
- Live provider behavior, cost, rubric calibration, accuracy, fairness and prompt-injection resistance were not empirically validated. Schema checks establish shape/range, not truth. No automated employment decisions are appropriate.
- Exports resolve question wording from the current bank; exact historical question wording is not versioned. Role/seniority/question-set changes can invalidate completion until a retake.
- Desktop Chromium was exercised; Firefox, Safari, mobile and assistive-technology testing are unfinished. The five-minute video and assessment form submission remain the candidate's separate work.
