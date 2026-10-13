# Native implementation record

Approved spec: docs/superpowers/specs/2026-10-13-researchflow-mature-v1-design.md
Approved plan: docs/superpowers/plans/2026-10-13-researchflow-mature-v1-implementation.md
Baseline: 268160c88d9ab67fb314eb3b01f87fcfffe9e743
Branch: reference/mature-v1. Master is unchanged.

The user approved Native: main agent implements all tasks continuously; one fresh independent whole-branch reviewer at the end.

## Verified tasks

Tasks 1–12 implemented and verified. Task 13 is starting; Tasks 14–20 remain.
The original 58 tests passed before changes. Real database tests use PostgreSQL 16.15 and pgvector in GitHub Actions; local skips are never counted as database verification.

| Task | Verification evidence |
| --- | --- |
| 1 Provider boundaries | RED 5 failures; GREEN 68 tests on Python 3.11 and 3.12 |
| 2 Evidence ledger | RED before implementation; GREEN 75 tests |
| 3 Claim extraction/Chat | RED before implementation; GREEN 89 tests, later evidence binding regression RED→GREEN |
| 4 Claim verification | RED before implementation; GREEN 97 tests |
| 5 Report/CLI | RED before implementation; GREEN 105 tests, all four CLI fixtures actually run |
| 6 Persistence/migrations | CI 38386089140/job115258125270: 112 passed, real upgrade/downgrade/upgrade |
| 7 Parsing/safe fetch/arXiv | RED 23 failures; GREEN 26 new tests, Chinese physical PDF pages and exact offsets |
| 8 Retrieval | CI RED 38387175860; real vector binding failure fixed; all retrieval tests passed in CI 38388255842 |
| 9 Worker/step receipts | CI RED 6 expected failures; CI 38388846237/job115267280774 GREEN 155 passed |
| 10 Auth/API/SSE | CI RED 7 expected failures; CI 38390272121/job115272070883 GREEN 162 passed |
| 11 Knowledge | CI 38390578236: 3 expected feature failures, 162 passed; implementation verification pending |

## Rulings

1. Host has no Docker and cannot run PostgreSQL installation. Real PostgreSQL verification runs on the authorized branch CI, with explicit version and vector extension checks. Cost if wrong: a mismatch between development and deployment environments; local skipped tests are reported separately.
2. Native terminal Git has no push credential. Use the authorized GitHub connector with compare-and-swap reference updates. Local per-task commits remain the original implementation history. Cost if wrong: remote publication snapshots are less granular.
3. Claim identity includes project, text, qualifiers and evidence binding fingerprints, preserving immutable input provenance when sources change. Cost if wrong: the same wording with different sources has separate identities.
4. The executor disconnected during Task 11 (409 environment_offline). Continue main-agent implementation through authorized GitHub tree/commit writes and actual CI, keeping this record in the branch. Restore/synchronize the local worktree if available again. Cost if wrong: local CLI and visual inspection cannot be asserted until restored; CI must supply actual verification and no native checks are invented.

## Scope and remaining checks

Complete all tasks in the approved plan. No merge, paid deployment or live model fallback is authorized.
Real model quality and live embedding/arXiv smoke are not_run without configured credentials/connectivity.
CI must later expand to locked dependencies, Python 3.11/3.12 on Ubuntu/Windows, lint/type checks, real database failure/restart scenarios, Web build/Playwright, and Compose.

Task 11 knowledge core GREEN: CI38392021442/job115277872608 passed165 tests. Fixed review RED: CI38392096808 rejected the missing require_review input before implementation. Knowledge API is now connected; full gate pending.

Executor restored after Task 11. Pending local authored changes were backed up, the remote tree was restored into the isolated worktree, and native verification resumed. CI38392396244: 166 passed, including fixed review wait/resolution.

Task 12 complete: CI38403827137 passed168 Python tests and5 actual Chromium scenarios. npm ci, generated API contract drift check, TypeScript typecheck and production build passed. Desktop and390px screenshots were visually inspected. Actual browser tests covered PDF→research→report→anchored original→knowledge→explicit follow-up; invalid citation failure; double start/refresh idempotency; background Worker/SSE updates preserving an open evidence drawer and unsaved input; refresh preserving the original250px scroll; filter preservation on back navigation. The refreshed-scroll regression was observed RED in CI38402145622 and GREEN in CI38403298215. The stale task cache regression was observed in CI38399810187 and resolved before navigation. Native executor remains intermittently offline; authoritative code and actual verification are preserved in this branch.

## Continuation verification
The native executor disconnected again (409 environment_offline) after the main implementation. Pending reversible changes are preserved through the authorized connector and verified by CI; no native command completion is inferred.

CI38426178282:204 actual PostgreSQL/backend tests and5 Chromium scenarios passed.
CI38429275388:actual Compose build/restart passed with original Blob bytes, report, knowledge and9 checkpoints. Windows Unicode/autocrlf and overlapping runtime clock regressions were reproduced then fixed.
CI38430638834:Ubuntu/Windows Python3.11/3.12 core checks all passed; real PostgreSQL213 tests passed and a newly introduced mixed-mode test failed before its fix.

Subsequent local contracts: reviewed knowledge context, source policy guard, request-limit input and versioned pricing were observed RED then GREEN;178 core tests passed,40 database-dependent cases explicitly skipped locally. Full final CI and independent review are pending.

Ruling: execute final reversible steps through the authorized connector while the native executor is offline. Cost if wrong: native wheel checks cannot be claimed; actual CI must supply verification.
Ruling: fingerprint source and key dependencies conservatively. Cost if wrong: a compatible patch can require a new run; old reports remain available.
Ruling: accumulate one locked DB active clock for overlapping Worker/preview runtimes, with per-operation monotonic deadlines. Cost if wrong: DB clock authority differs from a single-process counter, but avoids double charging concurrent active time.
