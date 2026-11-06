# CAR35 Colab handoff implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a verified CAR35 ZIP and standalone EDA/train notebooks, then remove only the original SupSign source.

**Architecture:** Pure CAR35 bundle verification/restoration plus a separate training helper and notebook builder. Historical V3 builders and archived notebook fixtures retain compatibility; legacy recipes do not change. Large artifacts and source deletion receipts stay private in the parent workspace.

**Tech stack:** Existing Python, zipfile, Pillow, PyYAML, pytest; gdown and Ultralytics already used by the project.

**Spec:** ../specs/2026-11-06-car35-colab-handoff-design.md

## Global constraints

- gdown only; no Drive mount or automatic upload.
- Preserve exact CAR35 split/IDs, checksum-bind archive and manifest, no training locally.
- Validate the ZIP before any source deletion; delete only resolved, explicitly named SupSign roots/files.
- Synthetic tests use temporary data; preserve user mobile/DESIGN.md.

## Review focus

- ZIP traversal, symlinks, duplicate members and wrong checksum must fail before publication.
- Swapped labels/images or taxonomy and incorrect manifests must be detected.
- Train must start from official pretrained weights and keep test evaluation opt-in.
- Resume must reject dataset/settings changes and preserve existing runs.
- Notebooks must execute standalone with no source checkout, source dataset or Drive mount.

## Task 1 Bundle and training helpers

Files: training/data/car35_bundle.py; training/experiments/car35.py; tests/test_car35_handoff.py.

- [x] Add temporary real-file fixtures and observe RED for restore, integrity checks, training/resume and exports.
- [x] Implement safe restoration, full verification, guarded training/evaluation and result export; run focused GREEN.

## Task 2 Archive and notebook handoff

Files: training/notebooks/car35.py; active CAR35 notebooks; notebooks/legacy historical SupSign notebooks; guides and generator entry point.

- [x] Package the actual completed CAR35 folder, verify all members/CRC and ZIP checksum, keep SHA sidecar.
- [x] Test standalone generated notebook cells with synthetic archive and inference/training stub; configure actual manifest/archive hashes after packaging.
- [x] Run full regressions and independent review; inspect the handoff paths/configuration.
- [x] Delete only validated original source roots/files after archive readiness; retain receipts and report actual disk savings.
- [x] Conventional commit application changes, no dataset/credentials/weights or push.

Evidence: 13 CAR35 handoff tests pass, including both standalone notebook workflows, cache artifacts and enabling final test after validation. Full Python regression: 375 passed, 3 skipped, 10 existing warnings. A fresh review found two Important issues; both were reproduced RED and fixed GREEN. Actual CAR35 also passes the new notebook verifier after removal of the original source. No real GPU training is claimed.

The 14,330,625,873-byte ZIP has 73,973 members, full CRC/source-hash validation and a separately checked ZIP SHA-256. SupSign deletion was limited to the known parent source roots/files, with resolved-path/reparse-point checks and archive readiness before recursive deletion. Data, private receipts and deletion logs remain outside the public application checkout. Active notebooks have no personal Drive URL; the user will upload and paste the link.
