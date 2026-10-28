# Interview preparation: explain and debug AI Pulse without AI

This is a study guide to the actual implementation. Read the code and run the application yourself before the interview. Aim for a 30-minute discussion, with enough time to make a small change.

## Architecture and relationships

React/Vite calls the FastAPI JSON API through `frontend/src/api.js`. SQLAlchemy stores SQLite data for the local pilot. `backend/app/main.py` registers routers, creates missing tables, restricts CORS and marks responses non-cacheable.

`backend/app/models.py`:

- `User`: login identity and password hash.
- `Organization` → `Department`: department belongs to an organization.
- `Membership`: links a user to an organization, department, permission role, job role and seniority.
- `Response`: answer, score, explanation and flags belonging to one membership.
- `Assessment`: one current completion record keyed by membership, with question IDs, completion time and mock/live provenance.

Permission role (`admin`/`employee`) controls access. Job role (`support`/`engineering`/`sales`/`manager`) chooses questions. They are different concepts. A consultant has a separate membership in each company.

## Authentication and organization authorization

Start with `backend/app/auth.py`:

- `hash_password`: PBKDF2-HMAC-SHA256, random salt, 600,000 iterations. It is intentionally slower than SHA-256 to resist guessing.
- `verify_password`: constant-time digest comparison. It accepts inherited SHA-256 only so successful login can upgrade it.
- `make_token`: signs expiring HS256 JWTs with user subject and optional selected organization.
- `_decode`: validates signature, expiry, required claims and identifier types.
- `current_user`: resolves the user.
- `current_membership`: resolves that user's current database membership in the selected organization. Never trusts a role sent by the frontend.

`routes/auth_routes.py::login` returns memberships and upgrades legacy hashes. `select_org` verifies membership before signing the scoped token. `routes/dashboard.py::org_dashboard` requires the token membership's organization to equal `org_id`, and its role to be admin.

The inherited exploit was: authenticate as an admin in A, then request `/dashboard?org_id=B`. The old code authorized A and queried B. The fix binds authorization and query scope together. Ravi is the best example of why a global admin flag is wrong.

## Diagnostic lifecycle

`services/questions.py::questions_for` combines common and job-role questions and compares explicit seniority ranks. Alphabetic order does not model junior → mid → senior → lead.

`routes/diagnostic.py::get_questions` returns only question ID, type, text and option wording; scoring points stay server-side.

`submit`:

1. Builds the eligible bank from the authenticated membership.
2. Requires the exact question set once each; validates options, strings and size before model calls.
3. Scores every open answer into in-memory rows; nothing has been saved yet.
4. Acquires a membership mutation lock using a harmless row update.
5. Deletes old responses, writes the replacement set and updates the one completion record.
6. Commits once. Conflicts return 409 after rollback; failed AI calls return a separate 502/503/504 response.

Retakes are replacement, not history. There is no partial-save workflow. A failed retake leaves the existing assessment intact. Do not add partial submissions to dashboard denominators.

`services/assessments.py::completed_rows` is the common gate used by reports and dashboards: it requires an explicit assessment and checks exact current eligible IDs, no duplicates, valid scores/options/explanations/flags. Legacy answer rows do not prove completion.

## AI scoring

`services/llm.py::score_answer` uses deterministic mock fixtures or an HTTPS provider. It sends a trusted system rubric separately from JSON containing untrusted employee text. Requests have a 5-second connection and 20-second read timeout, a token output limit and no automatic retries.

`services/scoring.py::parse_evaluation` accepts plain JSON or an entire JSON fence, rejects duplicate fields and validates `Evaluation`: finite numeric 1–5 score, nonempty bounded explanation and allowed risk labels. Unknown fields, boolean/string scores and arbitrary risk labels fail.

`ScoringError` preserves a distinction between failed evaluation and weak performance. A fallback score of zero would silently misrepresent model failure as an employee result.

Validation cannot establish whether the model is fair or correct. Prompt separation reduces injection risk; it does not prove resistance. Mock fixtures are simulated and can describe behavior unrelated to the input. Live calls and provider retention have not been verified.

## Reports, dashboard and privacy

`routes/reports.py::build_report` computes the private report from complete rows only. Partial/empty data has no average, risks or recommendations. Recommendations are static role-specific guidance, not generated by the model.

`routes/dashboard.py::org_dashboard`:

1. Queries employee memberships in the authorized organization.
2. Considers each department and keeps distinct completed users.
3. Omits the department completely if fewer than five qualify.
4. Averages each employee's question scores, then those employee means. This gives equal employee weight despite role-specific question counts.
5. Counts each risk at most once per employee. Risk labels need five affected employees; summary risks draw only from eligible departments.

Example: one employee has 6 answers averaging 2, another has 8 averaging 4. Their department average is 3, not 44/14 and certainly not 44/2. Actual output still requires five employees.

Both report and dashboard use `utils.py::maturity_level`: below 2 Beginner, below 3 Exploring, below 4 Practitioner, otherwise Leader. Classification uses the unrounded mean.

A group of four must not leak through an organization total minus visible departments. Hence no full-company score and no suppressed-group risks in summaries. Threshold suppression is not differential privacy: repeated snapshots of an eligible group still create differencing risks.

## Deletion and export

`routes/diagnostic.py::delete_my_data` locks the membership, deletes all its responses and assessment, and commits once. There is no separate persisted report; `build_report` immediately becomes empty. Repeated deletion is harmless. Other memberships remain untouched.

`personal_scope` rejects caller-supplied query identifiers. Ownership comes from `current_membership`, not user or membership IDs in a request body.

`export_my_data` is the one original feature: a versioned JSON attachment containing only that membership's data and report, plus question wording from the current bank. The frontend creates a Blob/download and releases the temporary object URL. Exporting empty data is valid.

`frontend/src/pages/Report.jsx` confirms deletion, clears sensitive state after success, reloads the report and offers exports even when empty. `Dashboard.jsx` polls every five seconds and on focus, with manual refresh; authorization/refresh failure clears old results. No zero-latency cross-session update is promised.

## Tests and reproduction

Read these files in order:

| File | What it demonstrates |
|---|---|
| `backend/tests/conftest.py` | One seed template copied into isolated temporary SQLite databases; FastAPI dependency override. |
| `test_security.py` | Authentication, revocation, per-company roles, forged/invalid tokens, hash upgrades/salts. |
| `test_privacy.py` | Four/five boundary, partial/unscored/duplicate data, distinct employees, cross-org scope, math, risks and deletion threshold. |
| `test_diagnostic.py` | Input validation, replacement, AI failure preservation and simulated database commit rollback. |
| `test_personal_data.py` | Own-only export/delete, empty/partial states, multi-organization isolation. |
| `test_scoring.py` | Original malformed fixtures, strict schema, credentials, provider errors and message separation. |
| `frontend/tests/workflows.spec.js` | Real browser + HTTP backend + download + automatic dashboard refresh + roles and UI failure/retry. |

Run backend `python -m pytest -q` in its virtual environment. Run frontend `npm run build` and `npm run test:e2e`. Browser setup is `npx playwright install chromium`; CI installs OS dependencies too.

A passing unit test cannot prove a download works; the browser test checks a real download. Conversely, the browser's injected 502 only tests frontend handling, while backend scoring tests prove rejection and rollback.

## Tradeoffs to explain candidly

SQLite and direct table setup preserve a small inherited architecture. A real deployment needs migrations, stronger database invariants, query optimization and concurrency/load validation. There is no administrative membership-management UI.

Self-service deletion is per selected organization. It cannot erase downloaded exports, historical screenshots, backups or provider logs. New requests recalculate immediately; an open browser may display its last response until refresh.

Security work does not supply SSO, MFA, revocation, login limits or complete operational controls. Audit results are time-specific. Human review, provider governance and rubric validation remain necessary before using this for consequential decisions.

Codex's genuine mistake was reusing one salted hash in an initial seed optimization. It was corrected by hashing per account and adding a distinct-hash test. Template database copying preserves test speed without weakening the hashing behavior.

## Likely debugging and modification exercises

- **Dashboard says 403:** inspect selected token organization, membership existence and that membership's role. Do not simply relax the check.
- **Department disappeared:** check five distinct complete employees, department/organization scope, removed assessment/answer rows and changed eligibility.
- **Score exceeds 5:** inspect validation, denominator and whether someone bypassed `completed_rows`.
- **Model returns fenced JSON or a score of 7:** step through `parse_evaluation`; the former can pass, the latter must fail without saving.
- **Retake duplicates:** inspect the membership lock, old-row deletion and single transaction.
- **Deletion seems stale:** query `/reports/me` and `/dashboard`, then check browser polling/network failures and selected organization.
- **New question or role:** update `data/questions.json`, rank/role expectations and tests. Explain that existing completion may require a retake.
- **Change threshold to 6:** update `PRIVACY_THRESHOLD`, notice text, fixture/tests and documentation together. Do not update only the frontend.
- **Add a risk label:** update the `Risk` literal, trusted rubric, tests and display wording. Consider privacy implications.
- **Export CSV instead:** keep self-service scope, escape spreadsheet formula injection, and test download contents.
- **Persist history:** introduce assessment IDs/versioning and retention rules first; do not return to appending unversioned responses.

Suggested interview pacing: architecture/auth (7 minutes), diagnostic/AI (7), privacy/deletion/export (7), tests and live modification (7), limitations/client questions (2).
