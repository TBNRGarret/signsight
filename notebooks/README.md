# Supported CAR35 notebooks

| Input | Notebook | Preparation |
| --- | --- | --- |
| Raw 107-class YOLO ZIP with `data.yaml` and `train/valid/test` | [Raw107 → CAR35 → YOLO11s](SignSight_Raw107_CAR35_YOLO11s_Colab.ipynb) | Filters/remaps CAR35 and creates a new grouped development split on Colab, then EDA/train/export. One source link; no historical R3 patch. |
| Prepared CAR35 V4 ZIP, optionally plus reviewed R3 patch | [CAR35 EDA](SignSight_CAR35_EDA_Colab.ipynb) | CPU audit of the fixed prepared split. |
| Same prepared V4/R3 inputs | [CAR35 YOLO11s Train](SignSight_CAR35_YOLO11s_Train_Colab.ipynb) | GPU training on the fixed prepared split. |

Choose the notebook by the ZIP contents, not its filename. All notebooks run standalone with gdown and no Drive mount or repo clone. The prepared V4 pair has pinned manifest/patch checksums; those do not apply to a raw 107-class ZIP. The raw notebook creates a separately versioned benchmark and records the source ZIP checksum. See the [raw-input guide](../docs/training/raw107_car35_colab.md) or [prepared-input guide](../docs/training/car35_colab.md).

All runtime files stay in `/content`. Download result ZIPs before ending the runtime; saving the notebook does not save weights. Resume needs the complete existing run and unchanged settings. A different account/runtime downloads the dataset again and does not automatically restore previous checkpoints.

This is a development split with observed scene overlap and weak holdout support for some classes. Keep the limitations with any reported metrics; collect a separate car-view field test for independent claims.

Generate the prepared pair with `python -m training.notebooks.car35`; generate the raw-input notebook with `python -m training.notebooks.raw_car35`.

The [legacy directory](legacy/) retains the two historical SupSign V3 notebook files for earlier evidence and cache compatibility. Those notebooks use a different bundle format and are not the entry point for CAR35 V4.
