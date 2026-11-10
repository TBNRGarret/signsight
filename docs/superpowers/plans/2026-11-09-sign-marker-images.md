# Sign Marker Images Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task with TDD and a final whole-change review.

**Goal:** Show the approved traffic sign images on web/Flutter map markers and show reviewed photo evidence when a sign is selected.

**Architecture:** A checked-in visual catalogue maps explicit legacy and CAR35 aliases to approved SVG files. Generated Flutter PNGs share this catalogue. Existing authenticated evidence endpoints supply the selected photo; presentation owns cancellation, retry and fallback.

**Tech Stack:** JavaScript, Playwright, Flutter/Dart, existing FastAPI evidence API.

**Spec:** `docs/superpowers/specs/2026-11-09-sign-marker-images-design.md`.

## Global Constraints

- 35 CAR35 icons plus historical STOP; retain source colours and provenance.
- 48 logical pixel marker targets, separate revalidation status.
- No database/catalogue code migration or publication of dataset crops/private files.
- At most one reviewed photo is fetched per selection, through authenticated API.
- Work in canonical `signsight/` on the existing feature branch, as required by workspace instructions.

## Review Focus

- Ambiguous R.301e and W.245a records must not silently acquire a different meaning.
- Unknown codes and image decode failures keep usable text and a neutral fallback.
- Closing a popup, switching selection/account or signing out must not reveal stale evidence.
- Flutter circle annotations must not cover icon symbols, including after a style change.
- Browser SVG and Flutter PNG assets must resolve locally and retain licences/checksums.

### Task 1: Approved local assets and shared visual lookup

**Files:** `frontend/shared/signs/`, `frontend/shared/sign_icons.js`, `mobile/assets/signs/`, `mobile/lib/sign_icons.dart`, `mobile/pubspec.yaml`, `scripts/build_sign_assets.cjs`.

**Interfaces:** JS `resolve(code, name='') -> {key, url}` and `decorate(element, sign, document)`; Dart `SignIconCatalog.load()` and `resolve(code,{name})`, plus `renderSignIcon(code,{name}) -> Uint8List`.

- [x] Write lookup tests for 35 distinct CAR35 icons, legacy aliases, ambiguity/unknown fallbacks and real PNG output.
- [x] Observe RED with `node --test tests/frontend_sign_icons.test.cjs` and Flutter sign icon tests.
- [x] Bundle original approved SVGs and provenance; generate local JS registry, JSON and Flutter PNGs. Implement matching resolvers.
- [x] Verify GREEN, asset hash/provenance checks and existing sign icon tests.

### Task 2: Web markers and reviewed photo popup

**Files:** `frontend/map.js`, `frontend/index.html`, `frontend/shared/sign_popup.js`, `frontend/shared/sign_icons.css`, JS unit tests, `tests/browser/sign_marker_images.spec.cjs`.

**Interfaces:** `create({api, document, sign, onDetails, urlApi}) -> {element, dispose}`; map adapter accepts this popup handle as well as existing DOM popups.

- [x] RED: marker contains the resolved image with a separate status badge; popup fetches first reviewed image, rejects foreign URLs, cleans object URLs and ignores stale responses/account changes.
- [x] Implement local icon rendering, popup/photo loading, fallback/retry and cleanup without changing pin-picker dots.
- [x] GREEN: focused JS tests and existing map tests. Disposable browser checks cover real MapLibre markers, photo on click, close/logout and narrow-screen layout.

### Task 3: Flutter markers and selected photo

**Files:** `mobile/lib/api.dart`, `mobile/lib/reviewed_sign_photo.dart`, `mobile/lib/map_canvas.dart`, `mobile/lib/features/map/map_screen.dart`, `mobile/lib/app.dart`, Flutter tests.

**Interfaces:** `SignSightApi.signPhoto(id) -> Future<Uint8List?>`; `ReviewedSignPhoto(api, signId, sessionKey)` loads when selection/account changes and exposes retry.

- [x] RED: API only accepts local evidence content paths; widget handles empty/error/retry and selection/account changes; map layers place symbols above circles.
- [x] Implement authenticated photo retrieval, selected-sign photo widget, explicit alias rendering and corrected annotation order.
- [x] GREEN: focused Flutter tests, full Flutter tests and analyze; full JS suite and public-source policy.
- [x] Review visual captures at desktop/phone widths and Android emulator if available. Record scope and evidence in developer docs.
- [x] Final whole-change review; fix important issues with RED/GREEN, then conventional commit the verified feature. Do not push without a request.

## Evidence and review follow-up (2026-11-10)

- Lookup, popup lifecycle and Flutter photo tests were observed failing before their implementations. Additional RED/GREEN cases cover non-square PNG proportions, exact legacy alias guards, direct account changes, expired/uncertain status and phone popup action bounds.
- Whole-change review found three important issues: a loaded photo surviving a direct account switch, stretched rectangular PNGs and broad name matching for ambiguous legacy codes. Each was reproduced and corrected. Generated PNGs now preserve the SVG aspect ratio.
- Final JavaScript suite: 105 passed. Full Flutter suite: 61 passed; `flutter analyze` reported no issues.
- Full disposable browser suite: 22 passed. After preserving expiry/uncertainty text, both feature browser projects passed again. Desktop and phone captures were inspected; popup actions remain visible and content scrolls within the map.
- Browser fixtures seed two test users directly rather than spending registration quota. The regression harness now implements the adapter's existing `closePopup` method. Production rate limits remain unchanged.
- Full Python suite: 376 passed, 3 skipped (10 warnings, including non-interactive plotting). The asset-proportion regression passed. Public-source policy: zero findings; staged diff whitespace checks passed. All 36 staged SVG originals match their approved SHA-256, with Git text conversion disabled for those assets.
- Android native visual validation could not proceed because the attempted emulator was unauthorized in ADB. It was stopped. Widget/static checks do not establish native map style-reload restoration, physical-device, Safari or iOS acceptance; those remain device checks.
- Developer usage/provenance instructions: `docs/runtime/sign_marker_images.md`. No datasets, uploaded photos, runtime credentials or database migrations belong to this change.
