# Repository entry points and cleanup map

Canonical source is this checkout. Parent workspace owns runtime/private data.

| Area | Decision | Replacement / protection |
| --- | --- | --- |
| Seven notebook variants | Keep EDA + YOLO11s train; retire five historical artifacts | training/notebooks; synthetic cell execution, cache/download tests |
| CNN model/train/heuristic | Retire new predictions, HTTP 410 after auth | YOLO detect; historical CNN run schemas stay readable |
| GTSRB converters/evaluator | Retain as legacy baseline tooling | Existing converter/cache tests; never called by API |
| SupSign preparation and generic reader | Keep, organize under training | Versioned cache checks and checksum tests |
| ai_engine/config and catalog | Keep stable identities | Legacy IDs and persisted data never renumbered |
| Mobile app/controller | Extract feature parts and state owners | Same library/public API, widget/state/E2E tests |
| Web management | Keep URL, organize shared/staff assets | Auth and browser flows |
| Web user pages | Keep as test lab until native parity accepted | No premature removal; existing URLs stay |
| Public exporter | Replace one-time export with read-only tracked-file policy | Secret/private/runtime negative fixtures retained |
| Parent legacy source/runtime/academic docs | Outside cleanup | Do not synchronize, move or delete |

Verification records live in ignored `.cache/refactor_2026-11-01/`. The first Python baseline overlapped a builder edit and is not a clean baseline; use fresh post-change regression instead. Flutter baseline: analyze clean, 53 tests; JavaScript baseline: 95 passed. Task 2/3 regression: 319 passed, 3 skipped (retired-notebook-only checks were replaced by supported-notebook and reader/cache checks).
