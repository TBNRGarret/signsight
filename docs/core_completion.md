# Core implementation and acceptance

Updated 30 October 2026. Staff use the web management UI; ordinary users use Flutter. The laptop hosts FastAPI, SQLite, managed images and YOLO. Code implementation, automated verification and physical acceptance are separate statuses below.

| Area | Implemented | Acceptance still needed |
| --- | --- | --- |
| Contribution | Camera/library, upload → detect → select bbox → optional catalog label correction/reason → confirm label/pin → submit, review and exact approved map record; correction persists in the native draft/history | Physical Android camera/gallery, GPS, denied permissions and a complete real-photo review |
| Reports | Flutter evidence reports: confirm, removed, damaged, location/class correction and new evidence; own history and revalidation queue | Physical-device usability; reports retain their form only while the page remains open |
| Data lifecycle | Backend review, audit trail, duplicate handling and configurable revalidation policy; native user entry points | Field checks; elapsed policy time means data needs revalidation, not legal expiry |
| Map | Native MapLibre/OpenFreeMap, sign pictograms/status halos, destinations, car routes, nearby radius and route corridor controls | Real network/provider availability and native visual acceptance; no turn-by-turn, lane/direction or legal applicability guarantee |
| Recovery | Account/API-scoped native photo draft, upload retry, clear on logout/submission/discard, Android lost-picker recovery | Force activity/process closure and disk-full recovery on a physical phone; web drafts remain RAM-only |
| Model | SupSign CAR35 EDA/train notebook with gdown/cache; stable catalog independent of model indices; reviewed hash-bound mappings; append-only DB registry and provenance migration; dynamic web/Flutter selectors; mapped candidate inspection/benchmark tooling | Finish training, provide best.pt/reports, review the semantic class-to-catalog mapping, smoke-test candidate and migrate a copied personal runtime, independent car-view field evaluation |
| Runtime | Verified SQLite + managed-image backup/restore into a new directory; restored sessions revoked | Operator recovery drill and private off-laptop backup retention |
| Deployment | Laptop launcher supports paired TLS files; Caddy example and release signing configuration | Certificate/trust/domain/network setup, supervised service, production signing key and actual HTTPS deployment |
| Android/iOS | Android debug build; iOS project/permission declarations | Physical Android acceptance; iOS requires macOS/Xcode/signing and has not been built here |

## Automated evidence

- Python regression: **327 passed, 4 skipped**. Two opt-in existing-checkpoint tests run separately: **2 passed**, on CPU with temporary database/image storage. The positive sample is a legacy GTSRB ROI; this does not measure Vietnam street-scene quality. New coverage includes mapping order/hash validation, preserving old inference rows, registered catalog identity, dynamic corrections and competing report decisions from two staff accounts.
- JavaScript regression: **95 passed**. Noncontiguous catalog IDs remain stable in selectors; changing accounts during report catalog lookup/upload stops subsequent writes.
- Flutter unit/widget tests: **44 passed**, analysis has no issues. Includes correction draft/history, required reason/reconfirmation, unknown restored labels, light/dark layouts at text scales 1.0/1.3, retaining the map host across user tabs, a picker-specific pin layer, offline recovery and account isolation.
- Browser end-to-end: **20 web tests + 8 Flutter preview tests**, each covering desktop and phone viewports. The Flutter suite includes delayed autofill and plain-textarea adoption regressions in addition to contribution/report/revalidation flows.
- Android emulator integration: the updated corrected-label flow passed on 30 October. Authenticated capture/upload/detect → catalog correction/reason → label/pin → contribution → staff approval → exact corrected map record → evidence report. The main map remains mounted across tabs; the short-lived picker uses one GeoJSON pin layer rather than annotation-manager initialization. MapLibre uses a local style; camera, GPS and inference are synthetic. An initial test-only keyboard call and asynchronous native map lifecycle errors were exposed and fixed before the successful run. This does not replace physical camera/GPS or real-provider acceptance.

The same native flow passed with system dark mode and font scale 1.3. The emulator displayed a separate **System UI isn't responding** dialog in the captured enlarged-text screen; that screenshot does not establish clean native visual acceptance. Original font scale 1.0/night mode off was restored afterward, followed by another passing flow and a clean light-mode capture. Widget layout checks passed in both themes/scales; physical visual and accessibility acceptance remains pending.

All automated contribution/review tests use disposable accounts, SQLite/images and synthetic inference. Existing personal runtime data is not used for browser/native fixtures.

CI audit on 30 October: [run 41016898532](https://github.com/TBNRGarret/signsight/actions/runs/41016898532) passed Python, JavaScript, web browser, Flutter unit/analysis/build and Android build, but failed both Flutter browser logins. Trace snapshots showed password fill preceding Flutter's autofill adoption: the focused placeholder briefly contained the value, then the configured `current-password` input was empty. The browser helper now waits for the configured autofill ID before filling and still asserts the value and successful server login. A delayed-replacement regression covers this race without increasing timeouts, adding retries or bypassing authentication.

[The recheck](https://github.com/TBNRGarret/signsight/actions/runs/41018879568) passed both logins and the full desktop flow, then exposed the same adoption race in the phone's plain report textarea. Its helper now also waits for the engine's `autocapitalize="off"` configuration on fields without an autofill ID. A separate delayed-textarea regression covers that path on both viewports.

Web release and Android debug builds completed locally. Release task selection rejects missing signing variables; signing validation also passed with a disposable test keystore, which was deleted afterward. No production keystore or signed store release was created. The Caddy example has not been validated with a local Caddy binary or deployed.

## Run the training notebook

Open [SignSight_SupSign_YOLO11s_Colab.ipynb](../notebooks/SignSight_SupSign_YOLO11s_Colab.ipynb) in Colab. Set `SOURCE_URL` to the shared dataset ZIP, choose Drive/local output persistence, run preparation/EDA, inspect previews, then set `LABEL_REVIEWED=True` and run training. See [the notebook guide](supsign_yolo11s_colab.md) for cache/resume/export. Follow [model_activation.md](model_activation.md) to draft/review/bind the catalog mapping and test the candidate on a copied runtime. The currently served model is not automatically changed.

## Physical acceptance checklist

1. Start the laptop runtime following [deployment.md](deployment.md). Install a debug build configured for the laptop's LAN API. Use a user account; staff log in through the management web UI.
2. While parked, take a real road-scene photo. Check bbox/label and explicitly confirm the sign's location. Send it; confirm pending appears only in user history/staff queue.
3. Staff accept the contribution. Open it from user history; compare exact record, location and evidence on the map.
4. Send an evidence report. Confirm the original map record is unchanged before staff review, then inspect the reviewed result and report history.
5. Repeat with no signs, multiple signs, denied camera/location permission, offline upload/retry, application restart and logout. On Android, test OS destruction during the system photo picker.
6. Test destination search, car route and corridor/radius changes over the actual target network. Measure capture-to-result latency and per-class model errors using the independent field protocol; synthetic fixtures do not establish these measurements.

## Extensions outside the current core

Jetson capture/edge inference, continuous dashcam processing, full offline maps/synchronization, push notifications, turn-by-turn/voice guidance and scaled PostgreSQL/object storage are separate projects. No claim is made that these have been delivered. Docker is optional for the laptop setup.
