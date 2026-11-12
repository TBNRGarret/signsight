# Web deadlines and review recovery

> **For agentic workers:** Execute inline with TDD in the canonical feature checkout.

**Goal:** Close audit A05 for bounded web requests and recoverable staff review decisions, building on A03 receipts.

**Spec:** `docs/development/system_audit_2026-11-11.md`, A05. The user requested continuation. Keep existing staff layout, cookie authentication, private runtime and V4 unchanged.

**Architecture:** Shared auth transport owns a 15-second GET/HEAD deadline and 90-second write deadline, including body decoding. It supports caller AbortSignal and named superseded read slots; it rejects even if fetch ignores abort, cleans timers/listeners, and cancels old-account reads. No automatic POST retries. Mutations with network/deadline/5xx failure report an unknown outcome. Normal authenticated responses/errors stay compatible.

Staff review uses optional account/operation-scoped receipts on observation, report and duplicate review, atomically committed with the existing decision. Reuse the 0007 table; no new migration. Same key/resource/body returns original result, changed intent conflicts. The workspace freezes the attempted decision and comment, disables conflicting actions, and offers a manual same-key retry. Notes/pending requests persist across selections/queue refresh within the open page, clear on identity/role change, and do not persist to browser storage. After a 409, fetch the current exact record and show its status while preserving scratch notes. Account/policy edits receive bounded unknown-outcome errors but are not automatically replayed.

## Constraints / review focus

- Current-session 401 still clears UI; aborted/timed-out old work cannot clear a newer login or set a profile.
- Deadlines cover JSON and blobs, and cancellation never strands request promises. Do not leak timers/controllers or use cancel slots to supersede writes.
- Parallel review retries commit one decision and one set of effects. Authorization runs before receipt lookup; receipt failure/validation conflicts roll back together.
- A lost result, tab switch, row switch or queue refresh must not silently change a pending decision/comment, erase unrelated notes, or jump a newer selection.
- 409 may mean an already reviewed item or a pending report with a changed sign; distinguish by reading current state, not assuming success.
- All tests use disposable DBs/images/synthetic inference. No private migration, push, dataset/model/notebook changes.

## Task 1 — bounded request transport

Files: `frontend/shared/auth.js`, `tests/frontend_auth.test.cjs`.
- [x] RED: never-settling fetch and body; external/superseding/account cancellation; late 401/profile/body; unknown write result; HTTP compatibility and timer cleanup.
- [x] Implement owned abort/deadline with optional `timeoutMs`, `signal`, `cancelKey`; GET/HEAD slots only; preserve responseType and cookie semantics.
- [x] GREEN focused/full JavaScript regression.

## Task 2 — atomic review receipts

Files: `backend/app/services/write_receipts.py`, observation/report services and images/reports/duplicates endpoints; `tests/test_review_recovery.py`.
- [x] RED: observation/report/duplicate lost-response replay, changed key/body/resource, parallel retry, actor isolation and role rejection. Verify effects occur once.
- [x] Reuse optional Idempotency-Key validation and add a race-safe transaction begin helper. Pass receipt context into existing decision transactions before updates; return current original resource on replay.
- [x] GREEN focused review/image/report/migration suites, then full Python regression.

## Task 3 — preserve staff intent and reconcile

Files: `frontend/management.html`, `frontend/staff/management.js`, staff JS/browser tests.
- [x] RED: network failure after commit, manual retry, different-row notes, reload of pending queue, conflict after another moderator's decision, delayed old-session completion.
- [x] Add one result-check button, RAM-only notes/attempts, immutable review key/body, cancellation for superseded list/detail reads, and exact-record conflict reload. Preserve current table/inspector and role split.
- [x] GREEN browser acceptance at desktop/phone; inspect actual screenshots. Bound UI busy state without blind retries.

## Task 4 — verify and commit

- [x] Update audit and runtime docs with deadlines, same-page limits and migration compatibility.
- [x] Run Python/JS/web and Flutter/browser regressions as appropriate, source policy and whitespace checks; fresh independent review and RED/GREEN important fixes.
- [x] Conventional commit, clean checkout, no push. Logs: ignored `.cache/web-recovery_2026-11-12/`.

## Verification / review disposition

- Transport RED: five new tests failed against unbounded requests; GREEN23 auth tests. Staff state RED: three initial recovery tests failed. Backend review RED: six failed / one passed; GREEN39 focused moderation tests after correcting a second-actor fixture that incorrectly bootstrapped an existing admin again.
- Fresh review identified missing recovery access after a committed item leaves pending-only queues, discarded background conflict results, and missing uncertainty wording for account/policy network errors. All entered the fix pass: the wording issue is a required contract because a raw failure encourages retry despite unknown commit. Five additional JS RED cases cover three vanished queues, background reconciliation and edited policy retention; GREEN118 full JS tests. No deferred code findings.
- Unresolved attempts now have a compact recovery entry outside the inspector, only while needed. Exact fetched/acknowledged status is cached per item, so reopening an old table closure does not revert it to pending.
- Python407 passed /3 skipped /10 existing warnings. JavaScript118 passed. Desktop/phone web28 passed; Flutter browser10 passed using the existing unchanged Flutter build. No Dart/model/notebook changes required.
- The expanded shared-loopback browser workload hit real register/login quotas in its first full run. The disposable browser server now uses bounded10x fixture quotas; production limiter code/limits are unchanged and Python quota tests remain green. No public reset/bypass endpoint was added.
- Inspector screenshots were inspected at desktop and narrow-phone sizes. Evidence uses synthetic images/inference; no physical Safari/Android, real WAN outage, private runtime migration or remote CI claim. Notes/attempts remain RAM-only and account/policy writes lack keyed replay. The existing0007 table suffices; no new schema revision.
