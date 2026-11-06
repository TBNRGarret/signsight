# CAR35 folder split implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a checked CAR35 development dataset from downloaded YOLO folders.

**Architecture:** New folder-only preparation module reuses audit_dataset, visual_hash, cluster_records and choose_splits, without altering notebook implementation fingerprints. Audit selected roots, deduplicate, group by dHash without filename blocks, remap labels and atomically publish a portable dataset. A separate verifier checks the materialized files.

**Tech Stack:** Existing Python, Pillow, PyYAML, pytest; no new dependencies.

**Spec:** ../specs/2026-11-06-car35-folder-split-design.md

## Global constraints

- CAR35 ordering, seed 42, target 70/15/15, dHash distance 4.
- Original files, old artifacts and live runtime remain unchanged.
- Source is exactly data.yaml plus train/valid/test folders; output outside them.
- No numeric filename grouping, no fabricated capture provenance or test metric.

## Review focus

- Duplicate bytes with differing out-of-scope labels must be quarantined too.
- Missing labels must never become negatives; labels must match image stems unambiguously.
- Distinct numeric filenames must not create a group; near duplicates must remain together.
- Single-group classes must stay in train; unavailable holdout coverage must be explicit.
- Refuse existing or overlapping outputs; copied source hashes and label hashes must verify.

## Task 1 Folder preparation and validation

Files: training/data/folder_dataset.py; tests/test_folder_dataset.py.

Interfaces: prepare_folder_dataset(source, output, *, classes=CAR35, seed=42, near_threshold=4, progress=None) -> manifest dict; verify_folder_dataset(root) -> summary dict. Source accepts only downloaded YOLO folder layout. Reports explicitly identify heuristic development splits.

- [x] Add synthetic tests for remapping/negative handling, conflicting duplicates, restricted input roots, grouping, rare coverage, deterministic split, unsafe output, existing output and verifier tampering.
- [x] Run tests RED because folder preparation is unavailable.
- [x] Implement audit, deduplication, grouping and atomic copying using existing helpers; report verified actual counts.
- [x] Run focused tests GREEN and regression tests; fix failures with regression coverage.

Execution evidence: 12 focused tests; full Python regression 362 passed, 3 skipped. The real Ultralytics consumer regression runs in a subprocess to isolate its global Pillow patches. Two rounds of independent code review found no remaining Critical/Important issues. The new folder-only splitter reserves strongest groups in train after actual data exposed deficient rare-class learning support with the legacy splitter; V3 notebooks and recipes remain unchanged.

## Task 2 Prepare and review actual dataset

Files: private parent .cache/dataset_prepare_2026-11-06 and data/vietnam_yolo/car35_v4_2026-11-06; public docs/training/car35_folder_dataset.md.

- [x] Run the new entry point on actual source with progress logging.
- [x] Independently verify all generated files, hash/group isolation and class support; inspect bounded positive/negative bbox previews.
- [x] Report actual split sizes, exclusions, class gaps, output path and train command; preserve the old checkpoint.
- [x] Run public-source policy and diff checks; stage/commit only implementation, tests and public docs after review.

Actual artifact: 36,980 images, 40,528 boxes, train/val/test 25,886/5,547/5,547. All 35 classes present, 26,096 stored groups, no repeated byte hashes or cross-split stored groups. Removed 4,243 duplicate copies; excluded 6 invalid annotations and 946 images with conflicting duplicate labels; retained 9,870 CAR35-negative images. Actual data and reports stay outside the public source checkout.

Visual review explicitly found likely shared locations/capture sequences across splits and mixed letterboxed scenes in one large dHash component. This artifact is development-only, not evidence of independent field generalization. End_no_overtaking and End_all_prohibitions each have only one test box. Report those limitations even though the integrity checks pass; no weights were trained or serving configuration changed.
