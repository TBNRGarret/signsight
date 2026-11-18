# ViTSD ZIP cleaning review on Colab

Open or upload [SignSight_ViTSD_Cleaning_Review_Colab.ipynb](../../notebooks/SignSight_ViTSD_Cleaning_Review_Colab.ipynb). Select a **CPU runtime**. This notebook mounts the user's Drive; it does not use gdown, Kaggle, Torch or model weights.

1. Run installation and Drive mount; approve access in Colab.
2. Find the existing dataset ZIP under `drive/MyDrive` in the Files panel. Copy its path into `DRIVE_ZIP_PATH`, for example `/content/drive/MyDrive/datasets/ViTSD.zip`. This field accepts a filesystem path, not a sharing URL.
3. Keep `COPY_ZIP_TO_LOCAL=True`: copy the ZIP once into `/content`, then read its members without extracting a second full dataset. The mounted source is read-only from the notebook's perspective. The runtime needs room for the ZIP plus reports.
4. Keep `MAX_IMAGES=None` for a full audit. A short trial with 200 images is explicitly marked partial and must not be presented as a full audit. Select exactly `yolo` or `coco`, never merge both exports.
5. Optionally supply `REFERENCE_MANIFEST_PATH`: the existing CAR35 V4 `manifest.json`, or a ZIP containing exactly one manifest. A manifest is sufficient for exact SHA-256 overlap; the CAR35 images are not needed. Without a reference the report explicitly says cross-source overlap was not checked. No reference path or private Drive URL is distributed with the notebook.
6. Run the remaining cells. The full decode/hash audit is cached by archive, implementation and options within the runtime. The dHash pass decodes images again and records a spanning forest of candidate links; it does not produce training groups or alter splits.
7. Download the final report ZIP or open its copy in `MyDrive/SignSight_Reports`. Extract it and open `index.html`. Send the report for review before dataset preparation or training.

The ZIP includes source audit CSVs, mapping candidates, quarantine decisions, exact duplicates, optional reference overlaps, source class counts and bounded bbox/near-pair previews. Every mapping remains unapproved. Class counts describe geometrically valid source boxes, including some boxes in otherwise invalid annotations; they are not cleaned training counts. Missing/invalid annotations never become verified backgrounds. Duplicate images with conflicting annotation/status are quarantined conservatively.

Only report ZIPs are written to Drive, with unique names and no overwrite. Source ZIPs, images, labels, existing train/val/test assignments and serving checkpoints are unchanged. Neither filename nor dHash proves independent trips; reference hashes do not detect same-scene overlaps across datasets. The report is **not a training dataset**, and the notebook never starts training.

Saving the notebook does not preserve `/content`. Restarting the runtime requires staging and auditing again unless the runtime's verified files remain. Keep the exported report. For an interrupted local copy, use a new staging path or remove only its owned `.part` file; do not delete the source archive.

Regenerate and test from the source checkout:

```powershell
python -m training.notebooks.vitsd
python -m pytest tests/test_vitsd_review.py tests/test_vitsd_notebook.py -q
```
