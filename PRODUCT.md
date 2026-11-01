# SignSight

<!-- impeccable:product-schema 1 -->

## Platform

web

This file holds shared product truth for SignSight. Web management and the Flutter user app are equally important; neither is a secondary product. The platform value above governs the web interface in `frontend/`. For work in `mobile/`, also read `mobile/PRODUCT.md`, which scopes native platform guidance without duplicating shared product facts.

## Users

- Ordinary users discover recorded traffic signs, explore destinations and car routes, contribute photo evidence, and follow the status of their contributions and reports through the Flutter app.
- Managers review contributions and evidence reports, maintain sign records, and handle duplicates and revalidation through web management.
- Admins additionally manage accounts and configuration through web management.

## Product Purpose

Build and maintain a reviewed, evidence-backed traffic sign map. Help users discover recorded signs near a location or route and contribute corrections and new observations.

Success means a contribution can move from photo capture through explicit label/location confirmation and staff review to the correct map record, with evidence and review history retained. Model output and unreviewed submissions must remain distinguishable from approved data.

## Positioning

The current mechanism combines backend YOLO detection, user confirmation of the sign label and location, staff approval, and ongoing evidence reports and revalidation. Map data comes from reviewed SignSight records; the basemap does not automatically populate the sign database. No comparative superiority or field-accuracy claim is established.

## Operating Context

- SignSight is the COS40006 Computing Technology Project B capstone. This checkout is the canonical application source; academic/private documents and existing personal runtime data live in the parent workspace.
- Ordinary users use the Flutter app. Managers and admins use the web management interface. The legacy user web pages remain for checking flows not migrated to Flutter.
- The documented local setup hosts FastAPI, SQLite, managed images, and YOLO on a laptop. The Flutter app and web interface share the API and review lifecycle.
- Current implementation: Flutter/Dart with Material 3 for the user app; HTML/CSS/JavaScript for web management; Python/FastAPI for backend services; YOLO for detection.
- MapLibre and OpenFreeMap provide the map; Photon provides place search and OSRM provides routing. These services require network access. Device camera and location permissions affect capture and positioning.
- Capture and field acceptance are performed while parked. GPS and EXIF provide suggestions; the user confirms the sign's actual location.

## Capabilities and Constraints

### Contribution and review

- Capture/select photo → upload and detect → select detected sign → confirm label and pin → submit → staff review → approved sign appears on map.
- Preserve user, manager, and admin roles and shared authentication. Staff work queues do not belong in the ordinary user's app.
- Users can inspect their contribution history and submit evidence reports for confirmation, removal, damage, location/class corrections, and additional evidence.
- A submitted report does not directly change an approved map record. Revalidation age means the data needs checking; it does not establish a sign's legal expiry.

### Map and recovery

- Support nearby sign discovery, destination search, car routes, and configurable nearby radius/route corridor.
- Routing starts from the point being viewed; the user can use GPS to move to their current position first.
- Native contribution recovery retains one draft scoped to the account and API origin, with retry using an existing upload when available. Web preview drafts are memory-only; report forms are retained only while open.
- Turn-by-turn/voice navigation, lane/direction applicability guarantees, continuous dashcam processing, full offline maps/synchronization, background submission, and push notifications are outside the current core.

### Model, data, and deployment

- YOLO detections require human confirmation and review. Automated fixtures and legacy ROI samples do not establish accuracy on Vietnam street scenes.
- The served adapter uses the project's 10-class taxonomy. The SupSign 35-class training candidate requires reviewed mappings and a tested migration before integration; do not swap incompatible weights directly.
- Preserve existing personal database, uploads, weights, credentials, and modified academic worklogs. Keep private data and academic documents out of the public application repository.
- Physical camera/GPS, permission denial, recovery, real-provider behavior, and independent field accuracy still require acceptance. iOS has not been built or accepted here.
- Production HTTPS deployment, production signing, store release, and source-code licensing remain open decisions or unfinished operational work. Do not imply that they have shipped.

## Brand Commitments

- Preserve the product name **SignSight**.
- Existing user-facing terminology is Vietnamese, including **Bản đồ**, **Đóng góp**, and **Của tôi**. Preserve its meaning and distinguish pending, approved, rejected, and revalidation states accurately.
- No new aesthetic direction or marketing claims were established during initialization.

## Evidence on Hand

- `README.md`: product overview, features, stack, and local entry points.
- `docs/contribution_flow.md`: contribution and review workflow.
- `docs/flutter_user_app.md`: user app behavior, recovery limits, build instructions, and native acceptance limits.
- `docs/web_and_management.md`: staff workflows and permissions.
- `docs/core_completion.md`: implementation and verification evidence, separately from remaining physical acceptance. Read its current contents rather than treating test counts as permanent product facts.
- `docs/local_development.md` and `docs/deployment.md`: source/runtime separation, deployment, and recovery procedures.
- `data/`, `notebooks/`, and `docs/supsign_yolo11s_colab.md`: taxonomy and model-development material. Weights, original datasets, runtime database, and uploads are not distributed with the public source.
- No confirmed testimonials, customer counts, production deployment evidence, or independent field-accuracy guarantees were supplied for product copy.

## Product Principles

1. Preserve the chain from evidence and human confirmation to review and publication.
2. Keep ordinary-user tasks and staff responsibilities clear while sharing one source of product truth.
3. Make pending work, recoverable failures, data freshness, and model uncertainty understandable.
4. Protect account boundaries and existing runtime data during development, testing, and recovery.
5. Describe verified capability precisely; separate implemented behavior, automated evidence, and real-device/field acceptance.
