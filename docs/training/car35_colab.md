# Train CAR35 V4 or the reviewed R3 revision on Colab

This guide expects a **prepared CAR35 V4 ZIP with a root manifest.json**. If your file instead has 107 class names and `train/valid/test` roots, use the [Raw107 → CAR35 notebook](raw107_car35_colab.md); do not replace V4 hashes with the raw ZIP's checksum.

Use the CAR35 ZIP prepared on 2026-11-06. Its 35 class IDs and train/validation/test splits are fixed. The original local SupSign source is no longer needed by these notebooks.

1. Upload the supplied prepared CAR35 V4 ZIP to Google Drive as a file, then enable sharing that permits downloading through its link. The original archive checksum is prefilled. `ALLOW_REPACKED_SOURCE=True` also accepts a differently compressed ZIP only when its root manifest matches the independently pinned hash. Every image/label hash, inventory, class count and split is still verified before training. The actual container hash is recorded in `source_archive_verification.json` and included in the result export. Set this option to `False` to require the original archive bytes too.
2. The notebooks now default to **reviewed R3 labels**, using the same V4 images/splits. Upload the small supplied R3 patch ZIP as a second shared file. Fill `SOURCE_URL` with V4 and `PATCH_URL` with the patch. Both archive checksums and the new manifest checksum are prefilled. Set `APPLY_REVIEWED_PATCH=False` only to reproduce baseline V4, which needs no patch link.
3. Optional CPU EDA: upload [SignSight_CAR35_EDA_Colab.ipynb](../../notebooks/SignSight_CAR35_EDA_Colab.ipynb), configure those links and run all cells. Download the small EDA report ZIP. R3 has **36,980 images and 40,522 boxes**: 19 class replacements and 6 duplicate-box removals across 23 images. The 461 unreviewed nonidentical ViTSD candidates are not added.
4. Training: upload [SignSight_CAR35_YOLO11s_Train_Colab.ipynb](../../notebooks/SignSight_CAR35_YOLO11s_Train_Colab.ipynb). Select a GPU runtime, configure the same links and run all cells. It checks the small patch before downloading the large source, restores V4 once into staging, verifies/replays the patch, checks the new manifest and only then trains. It does not need a source checkout or create a second full extracted image dataset. The original V4 ZIP remains unchanged.
5. Defaults are official pretrained `yolo11s.pt`, image size 640, batch 8, 80 epochs, early stopping, validation only. Horizontal and vertical flips are disabled for directional signs. If memory is insufficient, start a new run with a smaller batch. Use a new run for the revision; V4 run resume is rejected against a changed manifest.
6. Download the exported result ZIP before ending the runtime. It contains best/last and periodic checkpoints, plots/results, request settings, evaluation reports, dataset identity and revision provenance. Send that ZIP for review before changing the serving checkpoint.

All dataset transfer uses **gdown**. There is no Drive mount, login flow, automatic upload or write to the user's Drive. Drive sharing/download quotas still apply. The official pretrained YOLO weights and Python dependencies are downloaded through their usual package/model mechanisms.

If a checksum check fails, the error now identifies the file and prints both expected and actual SHA-256. A complete mismatching download stays local for diagnosis instead of being downloaded again on every retry. A mismatch on the patch still stops: use the supplied **R3 ZIP**, not the superseded draft/R2, a folder or the full dataset. Patch archive identity is part of the reviewed revision provenance. A source manifest mismatch also stops; check that `SOURCE_URL` points to prepared V4 rather than raw SupSign, the patch or a training-result ZIP. Do not replace a trusted manifest hash with one learned from an unknown download. Each Drive file ID has a separate local download path, so correcting a link does not reuse another file's partial download.

On another Colab account/runtime, upload the notebook and paste the same file link. The dataset will download again unless the verified extracted directory already exists in that runtime. Saving the notebook does not preserve `/content`.

`RESUME=True` requires `RUN_DIR/weights/last.pt` and `training_request.json` for the same dataset/settings. It supports a run that remains in the runtime or a run you have fully restored yourself. Switching accounts does not automatically restore checkpoints. Checkpoints saved every five epochs are local files until you download the result ZIP. If interrupted, run the export cell when a checkpoint exists.

EDA's `EXPORT_REVISED_DATASET=False` avoids a second large ZIP by default. If you need a portable prepared revision, set it to `True` and keep the exported ZIP, checksum and `prepared_handoff.json`. This needs additional free disk space roughly equal to the extracted dataset. To use that already revised ZIP directly, supply its ZIP/manifest hashes and set `APPLY_REVIEWED_PATCH=False` (no additional overlay), with a distinct run name. Keep revision identity and source/patch provenance together.

Revision `car35_v4_reviewed_r3_2026-11-19` manifest SHA-256: `a62a286e5ce45a508d158423ec3efa559a857d385326f19c53280fc667f4f66c`. It was predicted after full local V4 image/label verification and replaying the real patch. That read-only preview does not mean a full corrected dataset ZIP or a trained model has been created locally.

`RUN_HELDOUT_TEST` defaults to `False`. Enable it only after selecting the configuration with validation. This V4 dataset remains a development benchmark: preview review found shared scenes across splits, and the two end-of-prohibition classes have only one test bbox each. Include those limits when interpreting metrics. Start V4 experiments from the official pretrained weights; earlier SupSign checkpoints may already have seen images now assigned to holdout.

The two notebooks under [notebooks/legacy](../../notebooks/legacy/) reproduce historical V3 caches. They are not the input path for the prepared V4 ZIP. Legacy recipe compatibility is preserved for old evidence; the current training workflow uses CAR35.

Regenerate the active notebooks from the repository with:

```powershell
python -m training.notebooks.car35
```

The embedded helper sources and archive/manifest identity come from `training/notebooks/car35.py` and `training/notebooks/car35_handoff.json`. Never insert a personal Drive link into the public generator/configuration.
