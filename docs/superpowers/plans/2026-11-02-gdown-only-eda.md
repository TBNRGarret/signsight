# Gdown-only Colab and dHash Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run both notebooks without Drive mounting/persistence, and show dHash evidence before proposing a new split.

**Architecture:** Keep the existing gdown ZIP downloader and checksum/cache verification. Use local /content storage, download report/cache/checksum explicitly, and add bounded dHash contact sheets to the read-only grouping renderer. Dataset V3 stays unchanged.

**Tech Stack:** Python, Pillow, pytest, standalone notebook builder, gdown 5.2.0.

**Spec:** User's 02/11/2026 instruction: use gdown only, no Drive mounting; prior approved grouping-review design remains in effect.

## Global Constraints

- Source/tests/commits in signsight/; preserve user DESIGN.md and all parent runtime artifacts.
- Dataset transfers use existing gdown helper, no Drive mount or account storage API.
- Results/cache are ephemeral under /content; instructions must not promise cross-runtime persistence/resume.
- Keep label/split/recipe compatibility unchanged; do not create V4 before reviewing dHash evidence.

## Review Focus

- A fresh notebook runtime cannot access google.colab.drive.
- Downloaded EDA report alone is not the prepared training cache; cache + checksum must be exportable.
- Groups outside the largest preview window still need dHash examples.
- Many filename collisions must not crowd out a dHash example or cause quadratic selection.
- Cross-account training must verify the same cache/manifest without re-auditing source ZIP.

### Task 1: local gdown-only workflow

**Files:** training/notebooks/cells.json; tests/test_supsign_training.py; generated notebooks; notebooks/README.md; docs/training/supsign_yolo11s_colab.md.

**Interfaces:** config creates WORK, PERSIST=WORK/'outputs', CACHE_ZIP and DATASET_ROOT without Drive imports. EDA DOWNLOAD_PREPARED_CACHE defaults True; export downloads report, optional dataset cache and its SHA-256 sidecar.

- [x] Replace mount tests with real config execution while Drive access is forbidden; observe failure.
- [x] Add cache-export test through the existing fresh embedded EDA/train flow; observe failure.
- [x] Implement local-only config and explicit cache/checksum downloads, retaining source/cache gdown paths.
- [x] Explain /content loss and same-runtime-only automatic resume; update handoff docs.

### Task 2: dHash evidence cannot be crowded out

**Files:** training/data/grouping_render.py; tests/test_grouping_review.py; notebook grouping guide.

**Interfaces:** summary['dhash_review'] gives available count, selected edge examples and sheet paths; report includes dhash_edges.csv and up to 12 selected pairs in sheets of four pairs. Existing per-group previews retain list return contract.

- [x] Test mixed-reason preview selection and global dHash examples outside max_groups; observe failure.
- [x] Select one edge per available reason before collision fill, with bounded fallback.
- [x] Export all dHash forest edges and sample by group/distance, bounded to 12; render an offline section.
- [x] Regenerate notebooks, run full Python suite, deterministic builder check and source policy; obtain fresh review and fix important findings with TDD.
- [x] Commit conventional changes, preserving user-owned diff; leave real dataset review/V4 for the next Colab artifact.

## Verification

- Full Python suite after reviewer fix: 343 passed, 3 skipped, 10 existing SQLAlchemy/Matplotlib warnings.
- Both config cells execute with Drive access forbidden; cache-export flow exercises report/cache/checksum downloads and cross-account gdown restore without resplitting.
- Fresh reviewer found outside-window sampling could be crowded out by 12 preview groups. The 13-group regression failed before a reserved slot was added; 17 grouping tests then passed.
- Deterministic generated notebooks, source-public policy (0 findings), and original user DESIGN.md diff verified. Synthetic dHash contact-sheet layout inspected.
- No real dataset split/model changed; V4 and cross-runtime checkpoint recovery are not implemented by this change.
