# Final MVP closeout — 19 November 2026

Scope: Flutter user app, staff web workspace, FastAPI/SQLite/image storage and server-side CAR35 detection on a laptop. The contribution/review/history/map/report core exists. Completion now depends on measured model quality, a working device build and a reproducible demo/runtime, rather than adding another client or database.

This list supersedes older completion snapshots for prioritization. Code implemented, synthetic automated tests, and real device/field acceptance are different evidence levels. Do not mark an item complete from an older screenshot or synthetic test alone.

## 1. Release blockers

| Work | Current evidence / gap | Done when |
| --- | --- | --- |
| CI | Python/JS/browser and Flutter jobs passed at `dd703e3`; Android failed twice on Maven Central HTTP 429. The dependency policy/cache/retry fix is documented in [android_ci.md](android_ci.md). | The final commit passes every job and produces a downloadable APK; no skipped Android check or ignored build failure. |
| Dataset corrections | A reviewed labels-only patch exists separately from CAR35 V4. It contains 19 class replacements and 6 duplicate-box removals across 23 images; it has not been materialized into a training dataset. | Apply it to a new writable copy, assign a new dataset identity, rebuild label hashes/counts/manifest, verify and archive with checksum. Preserve V4 and the current checkpoint. [Patch contract](../training/label_patches.md). |
| Training inputs | ViTSD substantially overlaps the current data. Its original test images overlap train/validation. The 461 usable nonidentical candidates still require visual/near-duplicate and label review; different bytes do not imply independent scenes. | Review candidates before importing; isolate related scenes across splits; explicitly document retained/excluded images and unresolved classes. Do not merge the entire source or use its original test as independent evidence. |
| Model acceptance | Current V4 is integrated but misses clear real-photo examples. Dataset validation metrics do not establish road-scene quality. | Freeze an independently collected, annotated car-view/phone test set before model selection; compare baseline and retrained candidate using per-class recall/precision, confusion, false positives and latency. Choose thresholds on validation, record sparse/unsupported classes, then evaluate the frozen test. Only activate a compatible, accepted checkpoint with rollback. |
| Installable Android demo | The project has release signing/HTTPS configuration; CI builds x64 emulator debug. Current physical camera/GPS acceptance and a signed user APK are outstanding. | Build a signed ARM-compatible APK against the chosen trusted HTTPS API; install it on a real phone. Keep keys private. Run the physical acceptance flows below and record build/model/API versions. |
| Runtime recovery | Backup/restore tooling exists. Local runtime evidence reported orphaned user references; a snapshot alone does not prove a successful restore. | Back up before repair/migration, inspect and resolve references deliberately on a copy, restore to a new directory, verify image hashes and revoked sessions, then repeat contribution → review → map. Keep an off-laptop private backup and matching model/catalog/mapping/configuration. |

The patch is a correction artifact, not a standalone dataset or a guarantee that retraining will resolve detection failures. Collect representative full scenes, negative images, small signs, blur/occlusion and varied lighting. Record capture sessions; neighboring frames must not become independent train/test samples.

## 2. End-to-end acceptance and fixes revealed by it

- [ ] Fresh user login/session restoration and expiry; guest/user cannot use staff actions. Logout/account switching cannot reuse another account's draft, pending result or image evidence.
- [ ] Physical camera and gallery, permissions granted/denied, GPS unavailable/inaccurate, manual pin confirmation. Upload real photos with zero, one and multiple detections. A no-detection result must clearly explain the current limitation; `Others` currently corrects an existing detection only.
- [ ] Label correction/`Others`, required reason and confirmation; send → pending history → staff view image/location → approve/reject → exact record and decision/comment in history. Inspect full evidence rather than accepting the model's label automatically.
- [ ] Interrupted upload and lost submission/review response: recover the original operation without duplicate writes; force app closure/reopen on Android. Staff recovery currently lasts only within the open page, so verify the visible limitation.
- [ ] Map pictograms and evidence photos on native style reload, navigation between tabs, light/dark and enlarged text. Nearby radius plus route corridor should show nearby OR route-adjacent signs, hide distant off-route signs, and survive slow/stale requests and provider outages.
- [ ] Finish or explicitly reduce scope for multi-detection submission from one image, route/corridor changes retaining the destination, and a convenient staff position preview. Older plans list these; inspect the actual flow before treating them as complete.
- [ ] Report removed/damaged/wrong class/wrong location, staff decision and user history. Revalidation time marks stale data, not legal expiration. Proximity to a route does not establish direction/lane applicability or an enforceable speed limit.
- [ ] Measure upload, inference, nearby/route and moderation timing with real phone photos and representative synthetic record counts. Record device/network/sample size and p50/p95; add a bounded inference capacity policy if requests accumulate. Fix demonstrated bottlenecks and freeze acceptance after the last code change.

## 3. Operations and targeted maintenance

- [ ] Verify trusted HTTPS from the demo phone, firewall/network reachability, non-reload service startup and restart after failure. Test actual Caddy/TLS configuration if selected; prepared example files are not deployment acceptance. SQLite can remain for this laptop MVP.
- [ ] Confirm the active checkpoint, catalog and mapping identities through a temporary smoke test, then the chosen demo runtime. Distinguish API unavailable, detector unavailable and external map/search/routing outage in the demo runbook.
- [ ] Bound or retire unused legacy full-list reads and eliminate the documented per-record query overhead where retained. Benchmark before considering a database migration.
- [ ] Add a dry-run inventory/retention policy for abandoned uploads and inference artifacts; preserve referenced evidence. Test disk-full handling using temporary storage. Do not prune the personal runtime during source cleanup.
- [ ] Reconcile `PRODUCT.md`, [core_completion.md](../runtime/core_completion.md), [deployment.md](../runtime/deployment.md) and the current launch guide with the final accepted build/model. Older test counts are historical; record fresh results without overwriting their provenance.

## 4. Handover

- [ ] Final architecture/API and install/run/backup/rollback instructions; model card with dataset provenance, class order, measured results, failure cases and limitations.
- [ ] Final report/paper tables and figures based on measured results, plus a short demo script, screenshots/video and a fallback recorded demonstration. Keep academic/private documents outside public source.
- [ ] Release commit passes policy/tests/Android build, installation is reproduced from the documented artifact, and the demo uses separate accounts/data from development. Freeze features after this rehearsal.

Recommended order: CI → corrected dataset and independent test collection → training/evaluation alongside Android/HTTPS setup → physical user/staff acceptance → runtime restore drill → final documentation and rehearsal. iOS distribution, Jetson, offline inference, turn-by-turn/voice guidance and additional model families remain extensions unless the required MVP evidence is already complete. iOS requires a separate macOS/Xcode/signing/device acceptance path.
