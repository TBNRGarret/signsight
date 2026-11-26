# Supported CAR35 notebooks

| Input | Notebook | Preparation |
| --- | --- | --- |
| Official MTSD fully annotated annotation ZIP, with official split lists | [MTSD inspection](SignSight_MTSD_Inspect_Colab.ipynb) | CPU class inventory and train-only speed-sign mapping candidates. Does not download image archives, approve mappings or train. Obtain MTSD from [the provider](https://www.mapillary.com/dataset/trafficsign); share the annotation ZIP via gdown or use a local runtime path. |
| Raw107 ZIP + reviewed correction/photo ZIP + existing raw107 `best.pt` | [CAR35 Fine-Tune](SignSight_CAR35_FineTune_Colab.ipynb) | Review mode exports a small train-only annotation pack; train mode checks the overlay, preserves test, and compares baseline/candidate on the same validation data. See the [guide](../docs/training/car35_finetune.md). |
| Raw 107-class YOLO ZIP with `data.yaml` and `train/valid/test` | [Raw107 → CAR35 → YOLO11s](SignSight_Raw107_CAR35_YOLO11s_Colab.ipynb) | Filters/remaps CAR35 and creates a new grouped development split on Colab, then EDA/train/export. One source link; no historical R3 patch. |
| Prepared CAR35 V4 ZIP, optionally plus reviewed R3 patch | [CAR35 EDA](SignSight_CAR35_EDA_Colab.ipynb) | CPU audit of the fixed prepared split. |
| Same prepared V4/R3 inputs | [CAR35 YOLO11s Train](SignSight_CAR35_YOLO11s_Train_Colab.ipynb) | GPU training on the fixed prepared split. |

Choose the notebook by the ZIP contents, not its filename. All notebooks run standalone with gdown and no Drive mount or repo clone. The prepared V4 pair has pinned manifest/patch checksums; those do not apply to a raw 107-class ZIP. The raw notebook creates a separately versioned benchmark and records the source ZIP checksum. See the [raw-input guide](../docs/training/raw107_car35_colab.md) or [prepared-input guide](../docs/training/car35_colab.md).

All runtime files stay in `/content`. Download result ZIPs before ending the runtime; saving the notebook does not save weights. Resume needs the complete existing run and unchanged settings. A different account/runtime downloads the dataset again and does not automatically restore previous checkpoints.

This is a development split with observed scene overlap and weak holdout support for some classes. Keep the limitations with any reported metrics; collect a separate car-view field test for independent claims.

Generate the prepared pair with `python -m training.notebooks.car35`; generate the raw-input notebook with `python -m training.notebooks.raw_car35`; generate the fine-tune workflow with `python -m training.notebooks.finetune`.

Generate the MTSD inspection notebook with `python -m training.notebooks.mtsd`. MTSD is the only planned external supplement for the next pilot; keep the Vietnamese CAR35 training data and validation/test splits. Inspect the annotation report before acquiring large image archives. Mapping suggestions need image/unit review, complete CAR35 annotations and exact/near duplicate screening before the existing fine-tune workflow can consume them. The MTSD inspector has synthetic fixture coverage; a real provider archive has not yet been supplied or validated.

The fine-tune notebook now defaults to a controlled 15-epoch pilot, accepts reviewed unchanged labels,
reuses a verified dataset in the same runtime and optionally probes development photos after training.
Use the [active-learning queue](../docs/training/car35_active_learning.md) to select new photos for human review.

The [legacy directory](legacy/) retains the two historical SupSign V3 notebook files for earlier evidence and cache compatibility. Those notebooks use a different bundle format and are not the entry point for CAR35 V4.
