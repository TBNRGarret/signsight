# Reviewed CAR35 label patches

`training.data.label_patch.create_label_patch` exports small, image-free correction overlays from a verified CAR35 V4 directory. It does not rewrite the source dataset or produce a train-ready dataset. Use it only after inspecting the original pixels; cross-dataset disagreement alone is not a reviewed correction.

Each edit supplies `image_sha256`, a physical zero-based `line_index`, the expected `from_class`, `to_class` in the original CAR35 order, a nonempty `reason`, and `reviewed=True`. Pass the previously recorded `expected_manifest_sha256`; do not silently adopt a newly changed source manifest.

```python
from training.data.label_patch import create_label_patch

patch = create_label_patch(
    dataset_root,
    new_patch_directory,
    reviewed_edits,
    expected_manifest_sha256=recorded_manifest_sha256,
)
```

The function verifies the source manifest, affected image/label hashes, class token, bbox and safe paths before publishing. Repeated edits for one line, unreviewed entries, stale labels and source/output overlap are rejected. Class replacements preserve bbox text, line endings and other objects.

For a reviewed contradictory duplicate, set `action='remove_duplicate'` and `retained_line_index` to the unchanged existing box to keep; `to_class` is that retained box's class. The retained line must have an identical numeric bbox and cannot itself be edited/removed in the same patch. This removes the redundant line instead of relabeling it into a second duplicate. Schema version 2 records separate `removed_boxes` and `relabeled_boxes` totals. A default `replace_class` edit changes only the class token.

Output contains corrected files under `labels/{split}/`, `patch.json` binding each old/new label hash, `corrections.csv`, and instructions. It contains no images, model weights or credentials. Keep the exported artifact in private storage, outside the public source checkout.

The overlay is **not a standalone training dataset**. Materialize it with the revision workflow below, preserving the original V4 ZIP/directory. Do not reuse old label caches or run/checkpoint metadata against the revised labels. Corrections to validation/test labels change the evaluation reference and must be documented; unchanged split membership does not establish independent field evaluation.

## Materialize a reviewed revision

`training.data.car35_revision.restore_car35_revision` takes the original V4 archive, a patch archive and a new output path. All input checksums are required. It restores V4 once inside an owned temporary directory, regenerates the patch from the reviewed edit instructions, compares the supplied patch metadata/label bytes, then applies those labels only within staging. Hashes, class counts and missing-class lists are recomputed for a distinct `car35_reviewed_development_v1` manifest. Every image hash, group, class order and split stays fixed. Failed verification never publishes the output directory.

```python
from training.data.car35_revision import restore_car35_revision

info = restore_car35_revision(
    original_v4_zip, reviewed_patch_zip, new_output_directory,
    expected_sha256=v4_zip_sha256,
    expected_source_manifest_sha256=v4_manifest_sha256,
    expected_patch_sha256=patch_zip_sha256,
    dataset_version="car35_reviewed_revision_name",
    expected_manifest_sha256=reviewed_manifest_sha256,
)
```

`preview_car35_revision` verifies an existing V4 directory and patch read-only and predicts the exact manifest checksum without copying the image dataset. It explicitly reports `materialized=False`. `pack_car35_revision` verifies a materialized revision, exports ZIP + `.sha256`, refuses existing output and checks free disk space. Runtime YOLO label caches are excluded. Training refuses to resume an old V4 run against the revised manifest.

The revision preserves `provenance/v4_manifest.json` and `provenance/label_patch.json`. Verification reconstructs the complete expected manifest from those documents, so silently changed group/split/count metadata is rejected. Historical V4 reports/previews move under `provenance/v4_reports`; new root counts/summary describe the revision. Result exports retain the two provenance documents.

The active CAR35 notebooks support this path without cloning the repository. Their current default uses the reviewed R3 overlay on V4; supply both file links. To reproduce the original baseline, set `APPLY_REVIEWED_PATCH=False`. See [the Colab guide](car35_colab.md). This revision changes labels only; no unreviewed ViTSD candidates are imported, no training is launched locally, and application serving is unchanged.

```powershell
python -m pytest tests/test_label_patch.py -q
```
