# Repository refactor — completion record, 01/11/2026

Implemented from the approved [plan](../superpowers/plans/2026-11-01-repository-refactor.md). New product work is in the [system improvement plan](system_improvements_2026-11-01.md); the refactor does not activate the new model.

## Delivered

- Supported notebooks reduced from seven to two. Builders no longer construct a combined notebook as an intermediate step; generated payload order is independent of filesystem enumeration. Retired notebook-only tests were replaced by supported-notebook execution tests, while generic reader/cache checks remain.
- CNN prediction writers return HTTP 410 after authentication. Historical CNN run/observation schemas and permissions remain readable; no database migration or row deletion was used.
- Flutter `app.dart` reduced from 1,624 to 55 lines and `controller.dart` from 832 to 370 lines. Screens and feature state live under `mobile/lib/app/` and `features/`; concrete controller facade methods preserve normal and dynamic callers. Session generations, draft sequencing and IndexedStack remain.
- Offline ML code lives under `training/data`, `training/experiments`, `training/notebooks` and `training/legacy_baseline`. Old import/CLI locations remain thin compatibility facades. API-only dependencies no longer require the training stack; YOLO and offline tooling have explicit requirements.
- Cache recipe V1 is accepted only for reviewed implementation/reader signatures; archive and image/label checks remain. New caches use V2 and reports expose `dataset_content_sha256`, separate from the raw manifest checksum. Relocating source ZIP metadata does not change content identity. Existing manifests/training requests are never rewritten to force compatibility.
- Shared/staff web assets are organized without changing HTML entry points. Legacy asset URLs remain server aliases; staff document authorization still checks filesystem identity. Web user pages remain available as a test lab.
- Technical docs now have an index and getting-started/runtime/training/testing/development groups. The historical source exporter was replaced with a read-only public-source policy check, also run by CI. Private dataset/checkpoint/worklog paths and unsafe source links are rejected.

## Verification

Local full Python regression: **326 passed, 2 skipped** before adding a separate Windows symlink characterization (that extra case skips when OS symlink privileges are unavailable). Subsequent targeted notebook/cache checks: **32 passed**. Existing migration reflection and headless plotting warnings remain; they are not test failures.

- JavaScript: **95 passed**.
- Flutter analysis: no issues; unit/widget/state tests: **53 passed**.
- Web browser flows: **20 passed**; Flutter browser flows: **8 passed**, desktop and phone viewports.
- Native Android emulator: **1 full flow passed**, including contribution, correction, pin, staff approval, exact map record and report. API/database, photo, GPS and inference are disposable/synthetic.
- Flutter web release and Android x86_64 debug builds passed. The normal APK was rebuilt after integration testing and points to the laptop API on emulator address `http://10.0.2.2:8000`; this is not an ARM64 phone release or a production-signed artifact.
- Public-source policy and relative documentation links checked. Fresh read-only review found and closed one Important policy allowlist regression; no remaining Critical/Important issues were reported.

Detailed logs/checksums remain private under `.cache/refactor_2026-11-01/`. No checkpoint, dataset, credentials or personal runtime artifacts are included here.

## Decisions and boundaries

1. Work stayed in the canonical checkout on a feature branch to satisfy workspace instructions. The pre-existing `mobile/DESIGN.md` diff was preserved byte-for-byte and excluded from commits.
2. The first Python baseline overlapped edits and is not a valid baseline. Fresh full and targeted regression results above replace it; its failures are not presented as pre-existing project failures.
3. Dart parts preserve one library/private access boundary; feature state has separate owners, while auth/request generations stay coordinated in the facade. This retains some library coupling rather than introducing another framework.
4. Known V1 caches and legacy baseline tools remain supported. Unknown recipes are refused. Compatibility carries maintenance cost but avoids forcing users to upload/audit datasets again or corrupting training provenance.
5. Web user pages and flat test organization remain until native parity and shared-fixture extraction justify removing/moving them. This keeps some transitional files and avoids premature feature/test loss.
6. The user-configured training notebook was copied to ignored private scratch before rebuilding public templates; private run-specific checksum values are not template defaults.

The existing model, database, uploads, taxonomy identities and private academic/worklog files were not replaced or migrated. Physical-device camera/GPS/network acceptance, reviewed 35-class mapping, car-field metrics and production deployment remain separate work, prioritized in the improvement plan. No reviewer minor findings were deferred.
