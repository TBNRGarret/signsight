# CAR35 folder dataset preparation

The user approved CAR35 with a new development split targeting 70/15/15 on 2026-11-06. Read only the supplied data.yaml and train/valid/test image and label folders; never scan the rest of the parent workspace. Preserve raw files, existing V3 artifacts, live runtime and user changes.

Reuse the tested source auditor, CAR35 order, dHash grouping and class-aware group splitter. A new folder preparation entry point must not change legacy notebook recipes. Remove byte-identical copies only when all source labels agree; quarantine invalid labels and contradictory duplicates. Retain verified empty labels and images with only out-of-taxonomy classes as negatives for CAR35, with explicit counts.

Execution finding: reusing the V3 splitter put End_all_prohibitions at 2 train / 216 val / 1 test boxes. The new folder-only splitter therefore anchors each class's strongest group in train and optimizes image/per-class ratios with a bounded holdout-coverage penalty. It never breaks dHash components or changes V3 behavior. Preserve the initial candidate privately and report rare holdout limitations.

Approaches considered: retaining the original split would retain known cross-split duplication; grouping numeric filenames reproduced unsupported giant groups. The approved approach removes numeric filename grouping and assigns connected dHash components (distance at most 4) intact. This is a heuristic development split; no claim of independent trips or verified physical signs. Rare classes remain in train and missing holdout classes are reported rather than duplicated.

Publish a new directory under parent data/vietnam_yolo with images/train,val,test and corresponding labels, data.yaml, manifest, per-class CSV, split/group summary, label previews and exclusions. Use copied images and atomic publication; refuse existing output. Hash-check copied images and generated labels. Verify disjoint hashes/groups, inventory, taxonomy and label geometry before completion. Keep source-to-output mapping and report implementation/settings identity. Exporting a ZIP for Colab is optional; no training or serving-model replacement in this task.
