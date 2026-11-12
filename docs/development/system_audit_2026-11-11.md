# System audit — 11 November 2026

Scope: canonical source at `368a15b`; FastAPI/SQLite, web management, Flutter user app, inference, training handoff, tests and laptop deployment. CAR35 V4 remains the approved training input. This audit does not re-split, retrain or activate a model, and does not change application behavior.

The core contribution/review product exists. The next work should improve failure recovery, consistent API boundaries and device acceptance before adding another client framework or replacing the database.

## Implementation follow-up — A01 and A02

The user selected these first two items for implementation after the audit. A01's authentication boundary is fixed in `df385b0`: both legacy reads now require a valid session; raw route-sign queries are limited to 20/minute/IP before geometry work. Authenticated response shapes, filters and read roles remain compatible. A12's legacy-list pagination/N+1 optimization remains outstanding.

A02's implementation gives nearby requests independent account-scoped ownership and one coalesced latest query. Center/radius/offset snapshots prevent stale-area results and mixed-area pagination. Query error ownership also protects current search/routing feedback, including requests begun while foreground work was active. Logout/new-account and disposal discard old work. A separate regression found that web popup auto-pan caused viewport refresh to remove its own selected marker; unchanged markers are now retained, while changed/absent markers and account changes still dispose photo URLs.

TDD observed the original API and map failures and the additional review findings before their fixes. Verification and remaining device limits are recorded in [the implementation plan](../superpowers/plans/2026-11-11-api-auth-nearby.md). Dataset V4, checkpoint selection and private runtime data were not changed. The findings below remain the historical audit evidence at `368a15b`; this section records their disposition rather than rewriting that evidence.

## Implementation follow-up — A03 and A04

The next implementation adds optional account/operation-scoped `Idempotency-Key` receipts for image uploads and observation batches, committed atomically with their result IDs. Same-key/same-content retries return the original resources; changed content conflicts. Concurrent retries, transaction/storage failures, restart and later moderation are covered using disposable data. Legacy unkeyed callers retain their old behavior.

Flutter saves an upload key and a frozen pending contribution before sending. Unknown submission outcomes retain the draft and expose a result-check action; retry uses the original intent, and stale account responses cannot clear a new draft. Native file drafts survive reopening; the existing web preview remains RAM-only, so closing/reloading it loses that draft. Report submissions and staff decisions do not yet use this contract. A05 remains outstanding and must not add blind POST retries.

Upload now runs as a synchronous worker handler, including bounded file reads, sanitization and database work with its request-scoped session used sequentially. A blocking-decoder concurrency test confirms the API event loop can continue; no phone-image p95 or load capacity is claimed. Migration `0007_write_receipts` is additive and was exercised only against temporary databases; personal runtime migration is still a deployment step. No model/dataset or private runtime files changed. Full evidence is recorded in [the recovery plan](../superpowers/plans/2026-11-11-contribution-recovery.md).

## Implementation follow-up — A05 (12 November 2026)

Shared web requests now have owned 15-second read/90-second write deadlines through body decoding, external cancellation and named superseded read slots. Old-account reads are cancelled without letting late responses change a newer session. Mutations are never automatically retried; timeout/network/5xx failures carry an explicit unknown-outcome contract.

Observation/report/duplicate review reuses atomic account-scoped receipts in the existing 0007 table. The staff workspace preserves frozen decisions and comments in RAM, supports manual same-key result checks, and keeps unresolved operations reachable even after they disappear from pending-only queues. Exact-record conflict reads remain authoritative after selecting another row. Account/policy edits show uncertainty and retain entered values, but keyed replay for those edits remains outside this change.

TDD and fresh review identified the disappeared-item and background-conflict gaps before their fixes. Verification is recorded in [the web recovery plan](../superpowers/plans/2026-11-12-web-recovery.md). Notes/attempts still do not survive a page reload or session/role change; this is same-page recovery. No private runtime, weights, datasets or notebooks changed, and physical-device/network acceptance and remote CI are not claimed.

## Original audit verification

All runtime probes used disposable SQLite, temporary managed images and synthetic inference. No personal database, uploads, credentials or actual checkpoint were used. Local evidence lives in ignored `.cache/system_audit_2026-11-11/`; the native controller probe is under `mobile/.cache/system_audit_2026-11-11/`.

- Fresh JavaScript regression: 105 passed; public-source policy: zero findings.
- Fresh staff browser tests: 4 passed in light appearance and 4 in dark appearance, each including desktop and phone Chromium viewports. Screenshots of the real management page were inspected. A temporary dark-test configuration initially used the wrong server working directory; correcting that audit-only configuration produced the passing run.
- Fresh Flutter unit/widget regression: 61 passed; static analysis: no issues. A separate controller probe reproduced the stale-nearby result below. It asserts the current faulty outcome as audit evidence, not desired behavior.
- Fresh Python regression: 376 passed, 3 skipped, 10 warnings (including non-interactive plotting). Passing existing regressions does not invalidate the separately reproduced findings below.
- No new native APK, device camera/GPS, TalkBack, Safari, actual-network provider, load, security penetration or remote GitHub Actions acceptance is claimed. The previous marker task's native check could not proceed because its emulator was unauthorized in ADB.

## Confirmed findings to address first

### A01 — P1: legacy endpoints bypass the newer authentication boundary

Locations: `backend/app/api/v1/endpoints/signs.py:72`, `backend/app/api/v1/endpoints/navigation.py:13`, and the router registrations in `backend/app/api/v1/api.py`.

With no session, `/api/v1/map/signs` returned 401, while `/api/v1/signs` returned 200 with all 40 synthetic records, including a removed record. `/api/v1/navigation/route-signs` returned 200 with 39 visible records. Neither legacy route has a user dependency or router-level authentication. Hiding a frontend page does not close these APIs. This is a boundary inconsistency; it is not evidence of administrator write access or disclosure of private uploaded images.

Next: decide the explicit read contract, then require authentication consistently or retire unused legacy endpoints. Apply a bounded response/work budget and rate limiting to route queries. TDD: guest requests, invalid/revoked sessions, authorized users and legacy compatibility. Do not just change navigation links.

### A02 — P1: Flutter can show old-area signs after a map pan

Locations: `mobile/lib/features/map/map_state.dart:18`, `:31`, `:45`; map `onIdle` in `mobile/lib/features/map/map_screen.dart`.

Reproduction: start nearby request A; pan to center B while A is pending; `refreshNearby` returns early because `mapBusy` is true; A completes and applies its results. The probe ended at center `(11,107)` with signs from `(10.7769,106.7009)` and only one request. Moving the center does not invalidate the old operation or queue a replacement.

Next: snapshot center/radius with each nearby operation, invalidate stale results, and coalesce a pending refresh for the newest view. Separate search/route/nearby operation ownership where necessary. TDD: slow A/fast B, repeated pans, radius changes, more-pages and logout. Do not clear busy flags from an obsolete request.

### A03 — P1: ambiguous write completion has no end-to-end recovery contract

Locations: `backend/app/api/v1/endpoints/images.py:35`, `:136`, `:153`; `mobile/lib/features/capture/capture_state.dart:280`; `mobile/lib/api.dart:46`.

The same synthetic photo uploaded twice produced two 201 responses with different IDs. Submitting the same detection twice produced 201 then 409. The uniqueness constraint correctly prevents a second observation, but the client treats a retry conflict as an error and retains its draft. If the server committed and the response was lost, the user cannot distinguish success from failure through that retry alone. A new upload after a lost upload response also consumes extra storage.

Next: an account-scoped client request ID and payload identity for upload/submission, or an equivalent explicit reconciliation API. A same-key/same-payload retry should return the original result; changed payload must conflict. Client history reconciliation must clear only the matching completed draft. TDD: drop responses after commit, restart/retry, parallel retries, changed payload and cross-account isolation. Do not add blind automatic retries to POST operations.

### A04 — P1: upload image processing blocks the API event loop

Location: `backend/app/api/v1/endpoints/images.py:35–65` calls synchronous Pillow sanitization, file writes and SQLAlchemy work directly inside an async handler.

A controlled decoder probe recorded `decode_enter → decode_exit → concurrent_task_ran`; the decoder ran on the event-loop thread. The injected delay proves scheduling behavior, not the actual processing time of a phone image. Upload size/pixel/type checks and transactional cleanup are already present and should be preserved.

Next: isolate synchronous processing and database work in a correctly scoped worker/unit of work. Avoid sharing a session across concurrent tasks. Add concurrency tests demonstrating that a slow upload does not stall unrelated requests; then measure real-image median/p95. FastAPI does not automatically offload ordinary helper functions called inside async handlers: [official concurrency guidance](https://fastapi.tiangolo.com/async/).

### A05 — P1: the web request layer has no timeout/cancellation policy

Location: `frontend/shared/auth.js:35` awaits `fetch` without an internally owned deadline or abort controller. Staff decisions and list loaders await that request before releasing their busy state. Flutter has request deadlines; the web client is not equivalent.

Next: bounded read deadlines, cancellation for superseded reads, clear timeout/retry messages and recovery that preserves review comments. Treat a timed-out mutation as an unknown outcome and reconcile it using A03 rather than assuming it failed. TDD: a request that never settles, account changes during a slow read, lost review response and a retry after the server committed. This is source-confirmed missing behavior; no production network outage was induced.

### A06 — P1 capability gap: a missed detection blocks a valid contribution

Locations: `mobile/lib/controller.dart:105–116`, `mobile/lib/features/capture/capture_state.dart`, `backend/app/schemas/images.py` and the observation submission endpoint.

The app can submit only when `draft.selected` exists. The API requires an existing `detection_id`. An empty inference result offers a clearer/closer-photo retry but no manual path for an otherwise valid sign photo. Correcting a detected class is already supported; that does not cover a sign the detector missed entirely.

Next: allow a separate manual proposal with uploaded evidence, selected catalogue entry, optional manually drawn bbox and confirmed pin. Preserve the fact that it was manually proposed; do not fabricate an AI prediction or confidence. It must still enter staff review. TDD: zero detections, multiple manual signs, invalid boxes, ownership and approval/history provenance.

## Remaining work by area

P1 below means acceptance work required before a real-user pilot. P2 means a focused next pass, or a prerequisite to public/multi-user operation. Items explicitly described as recommendations have not been established as production defects.

| ID | Priority / area | Concrete work | Completion evidence |
|---|---|---|---|
| A07 | P1 / Android acceptance | Signed ARM64 build with the chosen API origin; actual trusted HTTPS or explicitly scoped debug LAN; camera/gallery cancel/denial, GPS denied/low accuracy, picker process death, offline/restart and logout/account changes. Check iPhone web image formats if that test path is retained. | Device/OS/build checklist, exact record/evidence after approval, failure logs and real elapsed times. Browser emulation and x64 debug build are insufficient. |
| A08 | P2 / moderation UX | Keep the existing table/master-detail workspace. Add location preview in the inspector, compare proposed/current pin and images, preserve notes during failure, and make conflicts reload the affected item without losing orientation. Add useful queue filters for sender/date/type only where the workflow needs them. | Two moderators handle a conflict; location/class/report decisions are made without coordinate guessing or repeated new tabs. Existing automatic first-row/next-item selection remains. |
| A09 | P2 / driving context | Record sign orientation/applicable direction, position accuracy and evidence date/source where known. Treat road-side/lane applicability as unknown until verified. Keep the current corridor described as proximity to route. | Opposite carriageways and parallel roads tested; no speed-limit or turn instruction inferred solely from marker proximity. Turn-by-turn/voice guidance remains outside this pass. |
| A10 | P2 / map interactions | Retain destination/route when changing only a search option; recompute the corridor when requested instead of clearing the route and requiring the destination again. Add explicit refresh state and last-update feedback. | Radius/corridor changes produce understandable results; slow queries and provider failures leave contribution/history available. |
| A11 | P2 / image and map performance | Reuse the authenticated thumbnail endpoint for small evidence previews, open full-resolution evidence on demand. Measure before adding caching. Diff native map annotations instead of clearing/rebuilding all circles/symbols on every scene update if profiling confirms jank. Bound inference queue/wait and per-user work; the detector lock currently serializes predictions but does not provide a capacity policy. | Real phone images and dense maps profiled; memory and upload/inference/query p95 recorded; overloaded requests fail clearly rather than accumulating indefinitely. |
| A12 | P2 / database/API scale | Retire or paginate the legacy full-list route and remove its per-record duplicate-count queries: the probe used 44 SQL statements for 40 records. Benchmark nearby, route and moderation queries; reduce repeated query-time lifecycle writes where justified. | Query counts and `EXPLAIN QUERY PLAN` on representative synthetic sizes; bounded results and stable concurrent moderation. Existing status index was observed in the plan, so this audit does **not** claim missing indexes. SQLite can remain. |
| A13 | P2 / storage lifecycle | Add a dry-run inventory for unattached uploads/abandoned inference runs, explicit retention rules, account storage quotas and a reviewed cleanup operation. Preserve evidence/history still referenced by accepted data. | Simulate disk-full and abandoned upload/retry; retained evidence is intact after cleanup and backup/restore. Never prune current personal data as part of source refactoring. |
| A14 | P2 / operations | Dedicated liveness/readiness for API/DB/detector, request IDs, structured timings and categorized errors; supervised laptop service and startup config validation; tested TLS/proxy configuration. | Restart/recovery drill and clear differentiation between API alive, provider unavailable and detector unavailable. Current authenticated `/ai/status` remains useful but is not a complete supervision interface. |
| A15 | P2 / recovery | Schedule and retain private off-machine backups, and restore to a new directory using matching weights/catalogue/mapping/configuration. Existing verified backup/restore commands should be exercised, not rewritten. | Restore drill, revoked restored sessions, matching image hashes and successful contribution/review/map flow on the restored copy. |
| A16 | P2 / review feedback | Show a clear accepted/rejected result and comment in the user's history, with exact-record deep link. Existing history does this; improve freshness with foreground refresh or a bounded poll and queue last-update indicator. | A user sees a staff decision without guessing whether a new submission is needed. Push infrastructure is optional, not required initially. |
| A17 | P2 / release and CI | Add regression cases for A01–A06; test current native icon/photo lifecycle through actual style reload. Keep synthetic E2E isolated. Separate fast BE/JS checks from the Flutter build dependency when restructuring CI. Add a physical-device acceptance/release checklist and rollback artifact. | New tests reproduce each defect before implementation; local suites and remote CI both verified for the release commit. This audit did not fetch current remote Actions status or build a new APK. |
| A18 | P2 / documentation and maintenance | Date capability/test snapshots and distinguish catalogue size, model class order and active runtime configuration. `core_completion.md` records older counts; `PRODUCT.md` still describes a legacy 10-class adapter, so reconcile with an inspected runtime before asserting its active model. Keep user web as a test lab until native parity is accepted, then explicitly decide its support scope. | One current run guide and capability matrix; no deletion of parent runtime/private material or blind synchronization into legacy source. |

## CAR35 V4 training and model integration

Use the existing V4 ZIP and notebook, with their current fixed checksums/splits. Do not block this work on V5. Run a small separately named smoke experiment, then the YOLO11s pretrained baseline (640, batch 8 as an initial fit, up to 80 epochs with early stopping). A 960 run is a later controlled validation experiment, not a mandatory change.

Before activation, review per-class precision/recall, confusion and false positives, with the recorded rare-class and scene-overlap limits. Choose operating thresholds on validation, retain the selected inference size/NMS/threshold settings with the artifact, then run the development test after settings are fixed. Inspect the result ZIP, bind the exact checkpoint/catalogue/mapping, and smoke-test on temporary data. Keep the current serving model available for rollback. The existing model-mapping checks and append-only catalogue/provenance are strengths to preserve.

A separately collected car-view set remains necessary for field claims. This does not invalidate V4 for development or prevent the capture/upload pipeline from being tested now. No new field metric, automatic activation or model superiority is claimed by this audit.

## UI technical review

Implementation integrity: **pass for role separation and a coherent existing system**, with interaction/recovery findings above. Staff use the web work queue; users use Flutter. Preserve the current identity and these roles.

Provisional source/render-based scores (0–4 each), not WCAG certification or physical-device acceptance:

| Dimension | Web management | Flutter user app | Evidence/limit |
|---|---:|---:|---|
| Accessibility | 2 | 2 | Web controls have labels, tabs have keyboard navigation, Flutter has text-scaling tests; no screen-reader/complete contrast audit. Some staff row targets are only 28px high. |
| Performance | 3 | 2 | Bounded staff pagination and lazy selected evidence; full-size image previews and native annotation rebuilds merit measurement. No device-frame/latency benchmark. |
| Theming | 3 | 3 | Both staff appearances rendered and inspected; paired Flutter roles/bundled day/night styles exist. Native icon/style reload needs acceptance. |
| Responsive / platform conformance | 2 | 3 | Desktop staff layout remains compact. Phone staff table compresses five columns and places the inspector after 25 rows; this is secondary to the desktop admin scope. Flutter uses Material navigation and system services. |
| Implementation integrity / adaptivity | 3 | 2 | Server roles and shared catalogue are explicit; Flutter map stale-result bug is confirmed. Tablet/landscape and native accessibility remain unverified. |
| Total | **13/20** | **12/20** | Conservative partial audit, not a shipping sign-off. |

Recommended UI sequence: `$impeccable harden` for timeouts/recovery and state ownership, `$impeccable adapt` for the secondary narrow staff table, `$impeccable optimize` after profiling, then `$impeccable polish`. These can be addressed individually or together after implementation scope is approved; repeat the audit after fixes. No visual redesign or framework migration is needed for these findings.

## Work order

1. **Close A01 and A02 with TDD.** They are confirmed source/runtime mismatches and can be fixed independently of training.
2. **Recover reliably from network failure:** A03–A05, preserving notes/drafts and distinguishing unknown write outcomes.
3. **Complete contribution fallback:** A06, then physical capture → upload → correction → review → exact map record → report acceptance under A07.
4. **Improve staff verification and driving context:** A08–A10. Preserve the distinction between a nearby record and a sign applicable to the current car.
5. **Measure and harden operations:** A11–A18; prioritize based on pilot evidence, with backup/restore before any live migration.
6. **In parallel, train V4 on Colab**, inspect the exported artifact and activate only after the compatibility/smoke checks above.

Do not start V5, switch to PostgreSQL/PostGIS, introduce Docker/Celery as a requirement, rewrite the frontend, add Jetson ingestion or implement continuous dashcam/voice navigation just to increase scope. Those are separate decisions once a measured need exists. The user-facing core should become reliable before it becomes broader.
