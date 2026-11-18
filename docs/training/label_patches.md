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

The function verifies the source manifest, affected image/label hashes, class token, bbox and safe paths before publishing. Repeated edits for one line, unreviewed entries, stale labels and source/output overlap are rejected. Only the class token is replaced; bbox text, line endings and other objects remain intact.

Output contains corrected files under `labels/{split}/`, `patch.json` binding each old/new label hash, `corrections.csv`, and instructions. It contains no images, model weights or credentials. Keep the exported artifact in private storage, outside the public source checkout.

The overlay is **not a standalone training dataset**. Materializing it requires a separate writable dataset copy, a new dataset identity/manifest, recomputed label hashes/class counts and verification before training. Preserve the original V4 ZIP/directory. Do not reuse old label caches or run/checkpoint metadata against the revised labels. Corrections to validation/test labels change the evaluation reference and must be documented; unchanged split membership does not establish independent field evaluation.

```powershell
python -m pytest tests/test_label_patch.py -q
```
