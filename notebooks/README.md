# Supported CAR35 notebooks

1. [CAR35 EDA](SignSight_CAR35_EDA_Colab.ipynb) — CPU; gdown downloads the prepared V4 ZIP, verifies its fixed splits and produces a small report.
2. [CAR35 YOLO11s Train](SignSight_CAR35_YOLO11s_Train_Colab.ipynb) — GPU; the same ZIP, official pretrained YOLO11s, validation, optional final test and downloadable results.

Upload the supplied CAR35 ZIP to Drive unchanged, permit downloading through its link and paste that link into `SOURCE_URL`. Both checksums are already configured. The notebooks run standalone after upload; no repo clone, original SupSign folders, Drive mount or re-splitting is required.

All runtime files stay in `/content`. Download result ZIPs before ending the runtime; saving the notebook does not save weights. Resume needs the complete existing run and unchanged settings. A different account/runtime downloads the dataset again and does not automatically restore previous checkpoints.

This is a development split with observed scene overlap and weak holdout support for some classes. Keep the limitations with any reported metrics; collect a separate car-view field test for independent claims.

See the [Colab guide](../docs/training/car35_colab.md). Generate the active pair with `python -m training.notebooks.car35`.

The [legacy directory](legacy/) retains the two historical SupSign V3 notebook files for earlier evidence and cache compatibility. Those notebooks use a different bundle format and are not the entry point for CAR35 V4.
