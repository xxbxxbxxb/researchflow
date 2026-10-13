# Native implementation record

Approved spec: docs/superpowers/specs/2026-10-13-researchflow-mature-v1-design.md
Approved plan: docs/superpowers/plans/2026-10-13-researchflow-mature-v1-implementation.md
Baseline: 268160c88d9ab67fb314eb3b01f87fcfffe9e743
Branch: reference/mature-v1. Master is unchanged.

The user approved Native: main agent implements all tasks continuously; one fresh independent whole-branch reviewer at the end.

## Verified tasks

Tasks 1–10 implemented and verified. Task 11 is in progress; Tasks 12–20 remain.
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
