# API read authentication and latest nearby results

> **For agentic workers:** Use superpowers:executing-plans with TDD. Work in the canonical existing feature checkout as required by the workspace instructions.

**Goal:** Close A01 and A02 from the approved system audit without changing dataset V4, API response shapes or the product's role split.

**Architecture:** Reuse the current session/role dependencies for both legacy reads. Keep the legacy list response compatible; rate-limit raw route queries. In Flutter, give nearby work its own account-scoped operation identity, one running query and one coalesced latest intent. Search/routing retain independent ownership. Apply results only for the current center/radius and never append pages from another area.

**Tech Stack:** FastAPI/SQLAlchemy, Flutter/Dart, pytest, Flutter tests, existing disposable Playwright fixtures.

**Spec:** `docs/development/system_audit_2026-11-11.md`, A01/A02, selected by the user. Authenticated users, managers and admins may read; unauthenticated/invalid/revoked/expired/inactive accounts must not execute either route's work. Read access does not grant staff mutations. Keep all current catalogue meanings, roles and runtime data.

## Global constraints and review focus

- Canonical `signsight/` only, existing feature branch; no legacy-source synchronization or private-runtime mutation.
- No model, split, training notebook, catalogue, evidence visibility or UI redesign changes.
- No stale read may run lifecycle mutation before authentication.
- Raw route-query rate limiting must happen before distance work; the full-list pagination/N+1 backlog remains A12.
- Nearby: slow A then B/C, radius changes, old failures, duplicate refresh, more-pages, search/route overlap and account changes must preserve the newest owner's state.
- Closing/canceling foreground search/route must not let an old nearby finally block clear a newer request's busy state.
- Public `refreshNearby` futures settle after the request chain; superseded requests do not strand awaiters.

## Task 1 — authenticated legacy reads

Files: `tests/test_legacy_read_auth.py`, `tests/test_navigation_map.py`, `backend/app/api/v1/endpoints/signs.py`, `backend/app/api/v1/endpoints/navigation.py`.

- [x] Write tests for both legacy routes: guest/invalid/expired/revoked/inactive credentials rejected before route work; user/manager/admin valid reads retain response shapes and filters. Add raw route-query rate-limit coverage.
- [x] Observe expected RED (currently anonymous reads return 200).
- [x] Reuse `get_current_user`, add route-query limiter before work, retain existing responses. Authenticate the existing validation test.
- [x] Run focused auth/navigation regressions; conventional commit (`df385b0`).

## Task 2 — latest nearby area and account isolation

Files: `mobile/test/nearby_state_test.dart`, `mobile/lib/features/map/map_state.dart`, `mobile/lib/controller.dart`.

- [x] Write delayed-response tests reproducing old-center results; add coalescing, radius, pagination, failure, foreground-work and logout/relogin cases.
- [x] Observe expected RED before implementation.
- [x] Add private query/job ownership in `_MapState`; keep one request active and only the latest queued area. Snapshot center/radius/offset, invalidate old-area display, and reset ownership on account clearing.
- [x] Preserve search and route results while nearby is pending; report busy until all current work settles. Keep pagination scoped to its loaded area.
- [x] Run focused/full Flutter tests, analyze and formatting. Run Python/JS/browser regressions and public-source checks. Update the audit with completion and remaining limits.
- [x] Fresh whole-change review; fix important findings with RED/GREEN, then conventional commit. No push without a request.

## Evidence

Test logs and task ledger live in ignored `.cache/api-auth-nearby_2026-11-11/`.

- API RED: 11 failed / 3 compatibility passed; GREEN: 72 focused auth/navigation tests, then 390 full Python tests passed (3 skipped).
- Nearby RED: 6 failed / 3 passed; first GREEN: 9 passed. Review reproduced error-ownership and stale-queued-area cases; three additional RED tests and a fourth ordering RED test were added, then all 13 nearby tests passed.
- Nearby error ownership uses the foreground generation captured by each intent. Intents created during active search/routing cannot overwrite that operation's error feedback. A current-account 401 still invalidates the session; old-account responses never do.
- Full web regression exposed an existing popup lifecycle defect: automatic pan triggers a viewport refresh, which previously destroyed every marker and its selected photo. A deterministic `loadSigns()` refresh reproduced it in both browser projects. The renderer now retains unchanged id/data marker handles and removes changed/absent handles; auth changes still clear all handles. Tests also verify absent-marker photo cleanup/revocation. Focused browser GREEN: 2; full web suite: 22 passed.
- Scope adjustment: add `frontend/index.html` and `tests/browser/sign_marker_images.spec.cjs` to task 2 for that reproduced map defect. No CSS or visual redesign change.
- Final regression: 390 Python passed (3 skipped), 105 JavaScript passed, 74 Flutter passed, 22 web browser tests passed and 8 Flutter browser tests passed against the final release web build. Flutter analyze reported no issues; formatting checked 47 files with no changes. Public-source policy and staged whitespace checks run before committing.
- Independent final review found no remaining confirmed Critical/Important findings; all 7 additional reviewer reproductions passed, including foreground error ordering, queued-area changes, account isolation and disposal.
- Browser acceptance uses disposable data and synthetic inference. Android/iOS device acceptance and remote CI are still pending; these results do not establish model accuracy or real-device/network reliability. No dataset, notebook, serving checkpoint or private runtime data changed.
