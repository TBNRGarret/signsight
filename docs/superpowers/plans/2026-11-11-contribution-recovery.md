# Contribution retry recovery implementation plan

> **For agentic workers:** Use superpowers:executing-plans with TDD in the canonical checkout. The user requested continuation of the audit work order.

**Goal:** Close A03 and A04: safely recover a lost upload/submission response and keep image processing off the API event loop.

**Architecture:** Optional `Idempotency-Key` headers identify account-scoped upload and observation operations. A durable receipt and its result are committed together. The same key and normalized payload returns the original result IDs; changed payload conflicts. Existing unkeyed callers remain compatible. Flutter saves request keys and the exact pending submission before sending and reuses them across retry/restart. No automatic POST retries. Use a synchronous upload handler so file/decoder/database work runs in FastAPI's worker pool, with the existing per-request session used sequentially.

**Tech stack:** FastAPI, SQLAlchemy/Alembic, SQLite, Flutter/Dart, pytest and disposable browser fixtures.

**Spec:** [System audit](../../development/system_audit_2026-11-11.md), A03/A04. Builder choices: receipts persist without expiry for this pilot; upload identity hashes original bytes and media type, excluding filename; submission identity uses canonical validated JSON. Keys are 8–128 safe ASCII characters. Replays return current representations of the original resources, including a later moderation decision.

## Constraints and review focus

- Do not migrate or mutate the user's runtime database, uploads, model or dataset. Verify additive migration against disposable data only.
- Keep existing authentication/ownership, sanitization, limits, atomic batches and cleanup on failure.
- An account's keys never identify another account's resources. Upload and submission keys have separate scopes.
- Concurrent same-key writes must produce one result and no orphan files. Changed content must conflict even after restart.
- A persisted uncertain submission remains immutable on retry, so changing the draft cannot silently submit a second intent. Clear only the matching completed draft; logout/disposal cannot clear another account's work.
- Preserve drafts after network failure and avoid presenting unknown write outcomes as confirmed failure. Retain compatibility with old version-1 drafts by assigning missing keys on restoration.
- A05 web deadlines and staff-write reconciliation are a separate next task; do not claim them fixed here.

## Task 1: Backend receipt contract and worker upload

Files: `backend/app/db/models.py`, `backend/migrations/versions/0007_write_receipts.py`, `backend/app/services/write_receipts.py`, `backend/app/api/v1/endpoints/images.py`, `backend/app/main.py`, `tests/test_write_recovery.py`, `tests/test_upload_concurrency.py`, `tests/test_migrations.py`.

- [x] RED: keyed upload/submission replay, conflict, account isolation, parallel retry, transaction failure and application restart; concurrency probe must run while image decoding is blocked.
- [x] Implement receipt lookup/fingerprint/atomic claim and resolve unique-key races after rollback. Clean up failed files. Move upload to a sync worker endpoint and retain size/type/decode checks.
- [x] GREEN: focused image/auth/migration tests. Check pre-existing resource IDs/hashes survive migration.

## Task 2: Persist Flutter retry intent

Files: `mobile/lib/models.dart`, `mobile/lib/api.dart`, `mobile/lib/controller.dart`, `mobile/lib/features/capture/capture_state.dart`, `mobile/lib/features/capture/capture_screen.dart`, `mobile/test/write_recovery_test.dart`, `tests/flutter_browser/user_app.spec.cjs`.

- [x] RED: lose successful upload/submission response, restore controller/draft, retry same key/body, clear only after success. Changed in-memory fields must not change a pending submission; account changes discard stale completion.
- [x] Generate and persist random request IDs with drafts; send the optional header through upload and contribute. Freeze the first submission payload before sending; retries use that snapshot. Legacy drafts get missing IDs once and save before any write.
- [x] GREEN: focused recovery tests, full Flutter tests/analyze/format and disposable contribution/review/map browser flow.

## Task 3: Verification, documentation and conventional commit

- [x] Update API/runtime run guide and audit disposition, documenting migration and retry limits.
- [x] Run Python and JavaScript regressions, Flutter/browser checks, staged whitespace and public-source policy.
- [x] Fresh final review; fix confirmed important issues via RED/GREEN. Conventional commit; no push.

Evidence: ignored `.cache/contribution-recovery_2026-11-11/`. Existing feature checkout is retained per the workspace instructions. No legacy-source synchronization.

## Results and acceptance limits

- Backend RED: 6 failed / 2 passed. Focused first GREEN: 36 passed. Final Python: 400 passed, 3 skipped (existing plotting/reflection warnings).
- Flutter RED: 4 failed / 1 passed; pending-action widget also failed before the UI change. Final full Flutter: 80 passed. File-based restart tests use separate store instances on temporary disk; wait for outstanding writes before fixture deletion. Analyzer clean, formatting 48 files/0 changes, release web build succeeded in 46.7s.
- JavaScript: 105 passed. Flutter browser: 10 passed, including dropped committed upload/submission responses on desktop/phone; retries return identical IDs/key/body and history contains one observation. Web browser regression: 22 passed. Maps/inference use disposable fixtures and synthetic predictions.
- Initial pending notice above the photo displaced visible controls. Moving it after the primary action preserved the action position. Browser screenshots use actual canvas scrolling; semantics-only scrolling does not establish the painted viewport. This is browser-preview evidence, not native-device visual acceptance.
- Fresh independent review found no confirmed Critical/Important issue. Its 12 backend tests include two additional concurrent same-key/different-payload probes. No deferred code finding.
- Migration is additive and verified on temporary databases. Personal runtime still needs migration with its existing configuration. Web drafts stay RAM-only; native physical-device restart/camera/network tests and remote CI remain pending. Reports/staff-write recovery and A05 are not included. No automatic receipt expiry or cleanup was added.
