# Others correction and map scope implementation plan

**Goal:** A user can correct an existing detection to Others, and sees only signs within the selected nearby radius or the current route corridor.
**Architecture:** Preserve the existing inference/correction/review flow. Add one reserved application-only label without changing the checkpoint-bound catalog hash or model outputs. Reuse backend geospatial queries and existing route response geometry; deduplicate the nearby/route union in each user map.
**Spec:** User confirmed on 15/11/2026: Others is only for already-detected signs; route display is nearby OR route, never distant AND outside route. Keep Flutter users and web staff; maintain the existing web integration surface.
**Execution:** Work in the canonical `signsight/` checkout as required by AGENTS.md. TDD for each behavior; use disposable databases and synthetic inference. Do not modify original runtime, model, dataset or model mappings. Do not push.

## Design decisions

- Reserved stable application ID 1000000, code OTHER, label Khác / Others. It is a manual correction, never a new YOLO output or invented prediction/confidence. Require the existing correction reason and renewed confirmation. Preserve original detection, bounding box and provenance. Staff can accept/reject the correction normally; accepted Others has confidence zero/uncertain and the neutral icon.
- The existing catalog SHA remains the identity of supplied model/catalog artifacts. The fixed manual label is published separately from those bound entries and registered with application identities. Reject supplied catalogs or model mappings that attempt to claim its ID/code.
- With no route, show nearby signs. With a route, show their union with route signs, deduplicated by record ID. A selected sign does not bypass spatial scope. An explicit history link can still center the map on its record.
- Backend radius filtering happens before counts/pagination, with bounding-box candidates and exact spherical distance. Preserve class/status/viewport filters.
- Route resets/errors remove old route-only markers. Stale nearby/route responses and account changes keep existing ownership guards. Preserve unchanged marker handles/popups on refresh.
- No manual no-detection submission, freeform new catalog class, automatic training, dataset changes, new map provider or redesign.

## Task 1: Others

Files: `ai_engine/catalog.py`, `backend/app/services/catalog_service.py`, `backend/app/services/observation_service.py`; existing web/Flutter selectors consume `/taxonomy`.

- [x] RED: catalog publishes Others without changing its old hash; reserved collisions and model targets rejected.
- [x] RED: upload/detect/correct-to-Others/review/map/history preserves original prediction, requires a reason and cannot be submitted without a detection.
- [x] GREEN: implement the fixed manual identity and register it without editing bound input artifacts.
- [x] GREEN: Flutter correction controller/widget proves Others is selectable and uses existing reason/confirmation/persisted retry flow.

## Task 2: Spatial scope

Files: `backend/app/api/v1/endpoints/maps.py`, `backend/app/services/map_service.py`, `mobile/lib/controller.dart`, `mobile/lib/features/map/`, `frontend/index.html`, `frontend/routing.js` and a small shared scope helper if needed.

- [x] RED: nearby radius filters before pagination; incomplete/invalid scope rejected; nearby + far-on-route retained, far-off-route omitted, no duplicate selected marker.
- [x] GREEN: implement backend radius query, Flutter scoped marker/list getter and web route-change hook/marker union.
- [x] Verify late results, clearing routes, selecting history records and filtering without destroying unchanged popups.

## Verification and demo

- [x] Run focused tests RED then GREEN, Python/Node regressions, Flutter tests/analyze and web build: Python 424 passed/3 skipped, Node 123, Flutter 85, analyzer clean, web build passed.
- [x] Check the rendered browser flow with synthetic disposable data: 32 desktop/phone browser tests passed. Physical/native device acceptance was not run.
- [x] Preserve the private demo copy before restart; original parent runtime unchanged. Standard verified backup found 7 pre-existing orphaned user references. A separate consistent DB/image preservation snapshot retains them; no clean-backup/restore claim or data repair is made.
- [x] Verify mapped V4 still loads and performs real inference without rebinding or changing its 35 outputs; live demo login/taxonomy/map/app checked.
