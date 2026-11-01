# SupSign Grouping Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export inspectable grouping evidence from the standalone CPU EDA notebook.

**Architecture:** A separate read-only module replays joins and compares partitions, then writes tables/contact sheets/HTML outside the verified prepared dataset. Notebook embedding automatically carries the module; preparation and cache identity code stay unchanged.

**Tech Stack:** Python, Pillow, CSV/JSON/HTML, pytest, existing notebook builder.

**Spec:** ../specs/2026-11-01-grouping-review-design.md

## Global Constraints

- All application changes in signsight/; preserve mobile/DESIGN.md and parent runtime files.
- CPU only; no training, split changes or model activation.
- Existing V1/V2 preparation/cache provenance remains unchanged.
- Reports are outside the dataset; graph evidence is a replayed spanning forest, not exhaustive or historical.

## Review Focus

- Dense identical hashes must not produce a quadratic edge export.
- Missing explicit capture metadata must not invent filename groups.
- Stored groups that disagree with reconstructed components must be clearly flagged.
- Paths/source labels must not escape the output or create HTML injection.
- Notebook export must include review assets in a fresh embedded runtime with no repo imports.

### Task 1: Diagnostic replay and offline report

**Files:** Create training/data/grouping_review.py and tests/test_grouping_review.py.

**Interfaces:** explain_grouping(rows, *, block_size=100, near_threshold=4, groups=None) returns edges/partition comparison; write_grouping_review(root, output, *, groups=None, max_groups=12, samples_per_group=6, progress=None) returns summary and writes report assets.

- [x] Write tests for hand-derived transitive edges, filename namespace collisions, explicit capture groups and bounded edge output; run pytest to see expected missing-feature failures.
- [x] Implement diagnostic graph replay, retaining current preparation behavior as an independent comparison oracle in tests.
- [x] Write tests for verified read-only dataset reporting, coverage/negatives, mismatch warnings, escaped HTML, bounded previews and unsafe output paths; see them fail.
- [x] Implement JSON/CSV/contact sheets/HTML; run tests/test_grouping_review.py and existing training/cache tests.
- [ ] Commit feat(training): export inspectable grouping review reports.

### Task 2: CPU EDA integration

**Files:** Modify training/notebooks/cells.json, generated notebooks, tests/test_supsign_training.py, notebooks/README.md and docs/training/supsign_yolo11s_colab.md.

**Interfaces:** EDA cell invokes write_grouping_review(DATASET_ROOT, EDA_ROOT/'grouping', groups=GROUPS); existing export recursively includes the folder.

- [x] Extend real embedded-runtime notebook test to execute grouping and inspect downloaded ZIP assets; run and observe failure.
- [x] Add guide/code cell with decode/replay progress and compact summary; regenerate both notebooks deterministically.
- [x] Document CPU/cache/report workflow and review-before-resplit boundary.
- [ ] Run full Python suite, notebook determinism and public-source checker. Review complete diff, preserving original user diff.
- [ ] Commit feat(notebooks): include grouping review in CPU EDA export.
