# Train the prepared CAR35 V4 ZIP on Colab

Use the CAR35 ZIP prepared on 2026-11-06. Its 35 class IDs and train/validation/test splits are fixed. The original local SupSign source is no longer needed by these notebooks.

1. Upload the supplied ZIP to Google Drive as a file, then enable sharing that permits downloading through its link. Upload the ZIP unchanged; do not extract/repack it because the notebooks bind its exact checksum.
2. Optional CPU EDA: upload [SignSight_CAR35_EDA_Colab.ipynb](../../notebooks/SignSight_CAR35_EDA_Colab.ipynb) to Colab. Paste the file link into `SOURCE_URL` in the configuration cell, then run all cells. The ZIP and manifest checksums are already filled in. Download the small EDA report ZIP.
3. Training: upload [SignSight_CAR35_YOLO11s_Train_Colab.ipynb](../../notebooks/SignSight_CAR35_YOLO11s_Train_Colab.ipynb). Select a GPU runtime, paste the same ZIP file link into `SOURCE_URL`, and run all cells. The notebook downloads and verifies the prepared data, without re-splitting it or needing a source checkout.
4. Defaults are official pretrained `yolo11s.pt`, image size 640, batch 8, 80 epochs, early stopping, validation only. Horizontal and vertical flips are disabled for directional signs. If memory is insufficient, start a new run with a smaller batch.
5. Download the exported result ZIP before ending the runtime. It contains best/last and periodic checkpoints, plots/results, request settings, evaluation reports and dataset identity. Send that ZIP for review before changing the serving checkpoint.

All dataset transfer uses **gdown**. There is no Drive mount, login flow, automatic upload or write to the user's Drive. Drive sharing/download quotas still apply. The official pretrained YOLO weights and Python dependencies are downloaded through their usual package/model mechanisms.

On another Colab account/runtime, upload the notebook and paste the same file link. The dataset will download again unless the verified extracted directory already exists in that runtime. Saving the notebook does not preserve `/content`.

`RESUME=True` requires `RUN_DIR/weights/last.pt` and `training_request.json` for the same dataset/settings. It supports a run that remains in the runtime or a run you have fully restored yourself. Switching accounts does not automatically restore checkpoints. Checkpoints saved every five epochs are local files until you download the result ZIP. If interrupted, run the export cell when a checkpoint exists.

`RUN_HELDOUT_TEST` defaults to `False`. Enable it only after selecting the configuration with validation. This V4 dataset remains a development benchmark: preview review found shared scenes across splits, and the two end-of-prohibition classes have only one test bbox each. Include those limits when interpreting metrics. Start V4 experiments from the official pretrained weights; earlier SupSign checkpoints may already have seen images now assigned to holdout.

The two notebooks under [notebooks/legacy](../../notebooks/legacy/) reproduce historical V3 caches. They are not the input path for the prepared V4 ZIP. Legacy recipe compatibility is preserved for old evidence; the current training workflow uses CAR35.

Regenerate the active notebooks from the repository with:

```powershell
python -m training.notebooks.car35
```

The embedded helper sources and archive/manifest identity come from `training/notebooks/car35.py` and `training/notebooks/car35_handoff.json`. Never insert a personal Drive link into the public generator/configuration.
