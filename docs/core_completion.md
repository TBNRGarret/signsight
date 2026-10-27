# Core implementation and acceptance

Updated 27 October 2026. Staff use the web management UI; ordinary users use Flutter. The laptop hosts FastAPI, SQLite, managed images and YOLO. Code implementation, automated verification and physical acceptance are separate statuses below.

| Area | Implemented | Acceptance still needed |
| --- | --- | --- |
| Contribution | Camera/library, upload → detect → select bbox → confirm label/pin → submit, review and exact approved map record | Physical Android camera/gallery, GPS, denied permissions and a complete real-photo review |
| Reports | Flutter evidence reports: confirm, removed, damaged, location/class correction and new evidence; own history and revalidation queue | Physical-device usability; reports retain their form only while the page remains open |
| Data lifecycle | Backend review, audit trail, duplicate handling and configurable revalidation policy; native user entry points | Field checks; elapsed policy time means data needs revalidation, not legal expiry |
| Map | Native MapLibre/OpenFreeMap, sign pictograms/status halos, destinations, car routes, nearby radius and route corridor controls | Real network/provider availability and native visual acceptance; no turn-by-turn, lane/direction or legal applicability guarantee |
| Recovery | Account/API-scoped native photo draft, upload retry, clear on logout/submission/discard, Android lost-picker recovery | Force activity/process closure and disk-full recovery on a physical phone; web drafts remain RAM-only |
| Model | SupSign CAR35 EDA + YOLO11s notebook, persistent Drive cache, grouped splits, validation/test reports and candidate inspection | Run EDA/label review/training, provide best.pt and reports, approve class-to-catalog mapping, migrate 10 → 35 classes with tests, independent car-view field evaluation |
| Runtime | Verified SQLite + managed-image backup/restore into a new directory; restored sessions revoked | Operator recovery drill and private off-laptop backup retention |
| Deployment | Laptop launcher supports paired TLS files; Caddy example and release signing configuration | Certificate/trust/domain/network setup, supervised service, production signing key and actual HTTPS deployment |
| Android/iOS | Android debug build; iOS project/permission declarations | Physical Android acceptance; iOS requires macOS/Xcode/signing and has not been built here |

## Automated evidence

- Python regression: **286 passed, 4 skipped**. Two opt-in existing-checkpoint tests run separately: **2 passed**, on CPU with temporary database/image storage. The positive sample is a legacy GTSRB ROI; this does not measure Vietnam street-scene quality.
- JavaScript regression: **89 passed**.
- Flutter unit/widget tests: **35 passed**, analysis has no issues. Includes offline draft restart/retry, API/account isolation, late responses after logout, disk failure, report payloads and compact layouts.
- Browser end-to-end: **20 web tests + 4 Flutter preview tests passed**, each covering desktop and phone viewports. The Flutter flow also checks pending reports, staff review and the revalidation queue.
- Android emulator integration: **1 passed**. Authenticated capture/upload/detect → label/pin → contribution → staff approval → exact map record → evidence report. MapLibre uses a local style; camera, GPS and inference are synthetic. Two earlier runs lost the VM connection; a clean emulator boot with software rendering completed the test. This does not replace physical camera/GPS or real-provider visual acceptance.

All automated contribution/review tests use disposable accounts, SQLite/images and synthetic inference. Existing personal runtime data is not used for browser/native fixtures.

Web release and Android debug builds completed locally. Release task selection rejects missing signing variables; signing validation also passed with a disposable test keystore, which was deleted afterward. No production keystore or signed store release was created. The Caddy example has not been validated with a local Caddy binary or deployed.

## Run the training notebook

Open [SignSight_SupSign_YOLO11s_Colab.ipynb](../notebooks/SignSight_SupSign_YOLO11s_Colab.ipynb) in Colab. Set `SOURCE_ZIP`, mount Drive, run preparation/EDA, inspect previews, then set `LABEL_REVIEWED=True` and run training. See [the notebook guide](supsign_yolo11s_colab.md) for cache/resume/export and model review. The new model is a candidate; the currently served taxonomy remains unchanged until an explicit tested migration.

## Physical acceptance checklist

1. Start the laptop runtime following [deployment.md](deployment.md). Install a debug build configured for the laptop's LAN API. Use a user account; staff log in through the management web UI.
2. While parked, take a real road-scene photo. Check bbox/label and explicitly confirm the sign's location. Send it; confirm pending appears only in user history/staff queue.
3. Staff accept the contribution. Open it from user history; compare exact record, location and evidence on the map.
4. Send an evidence report. Confirm the original map record is unchanged before staff review, then inspect the reviewed result and report history.
5. Repeat with no signs, multiple signs, denied camera/location permission, offline upload/retry, application restart and logout. On Android, test OS destruction during the system photo picker.
6. Test destination search, car route and corridor/radius changes over the actual target network. Measure capture-to-result latency and per-class model errors using the independent field protocol; synthetic fixtures do not establish these measurements.

## Extensions outside the current core

Jetson capture/edge inference, continuous dashcam processing, full offline maps/synchronization, push notifications, turn-by-turn/voice guidance and scaled PostgreSQL/object storage are separate projects. No claim is made that these have been delivered. Docker is optional for the laptop setup.
