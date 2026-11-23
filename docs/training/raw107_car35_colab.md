# Raw 107-class ZIP → CAR35 → YOLO11s on Colab

Use [SignSight_Raw107_CAR35_YOLO11s_Colab.ipynb](../../notebooks/SignSight_Raw107_CAR35_YOLO11s_Colab.ipynb) when the source ZIP contains `data.yaml` with 107 class names and `train/images`, `train/labels`, `valid/images`, `valid/labels`, `test/images`, `test/labels`. No prepared manifest or V4/R3 archive is needed.

1. Upload the notebook to Colab and select a GPU runtime. Run the dependency cell.
2. Fill `SOURCE_URL` with the shared **file** link for the raw ZIP. Keep `RAW_ZIP_SHA256=''` unless you have an authoritative checksum for this raw source; the V4 checksum is not applicable. Download uses gdown without account cookies or a Drive mount.
3. If a complete raw ZIP already exists in this runtime, set `LOCAL_SOURCE_ZIP` to that file path instead. The old helper could delete a checksum-mismatching download; an absent file needs one fresh download. Saving a notebook does not preserve `/content` across runtimes/accounts.
4. Run pipeline and preparation. Preparation hashes the source, validates ZIP paths and the 107-class catalog, checks free disk space, extracts into an owned temporary tree and audits source labels/images. It filters by the existing ordered CAR35 names, remaps IDs to 0–34, removes identical-byte copies only when all source labels agree, quarantines conflicting labels and groups near-duplicate images with dHash. Filename numbers do not establish capture groups.
5. Whole groups are assigned toward 70/15/15. The actual ratios and missing holdout classes are printed. Source splits are not treated as independent evidence. Images containing only excluded classes remain negatives for the CAR35 taxonomy. Temporary raw extraction is cleaned after preparation; the original ZIP remains untouched.
6. Review EDA/class counts and bbox samples before running train. Defaults: official pretrained `yolo11s.pt`, 640px, batch 8, 30 epochs, early stopping and no left/right or vertical flips. Reduce batch for a new run if GPU memory is insufficient. Validation runs after training; held-out test requires explicit opt-in after settings are chosen.
7. Download the result ZIP before the runtime ends. It includes best/last/periodic checkpoints, training settings, validation reports, EDA, manifest and source identity. Send it for evaluation before activating a checkpoint in the app.

The output uses the prepared CAR35 folder schema but has its own `DATASET_VERSION`, source archive checksum, preparation recipe and manifest. It is **not the historical V4/R3 benchmark**. The old R3 patch is bound to that old manifest and split, so it is not silently applied to this rebuilt dataset. Labels in the new dataset still need review; dHash groups do not prove independent trips or every possible scene separation. Collect a separate car-view field set for independent quality claims.

Repeated preparation in the same runtime verifies and reuses the prepared dataset without another raw download/audit. Changing seed/grouping/preparation code requires a new version/output. Resume needs the same manifest/settings plus `last.pt` and `training_request.json`; switching accounts does not recover them automatically. Do not resume a V4/R3 training run on this new split.

The standalone notebook embeds the folder preparation pipeline and reuses the existing CAR35 train/evaluate/export code. It does not replace serving weights, alter a personal runtime, mount Drive or upload outputs automatically. Generate it with:

```powershell
python -m training.notebooks.raw_car35
```
