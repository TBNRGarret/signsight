# Supported notebooks

1. SignSight_SupSign_EDA_Colab.ipynb — CPU; gdown, source audit, CAR35 preparation, report ZIP and prepared cache.
2. SignSight_SupSign_YOLO11s_Train_Colab.ipynb — GPU; restores reviewed cache without resplitting, fine-tunes YOLO11s, validates and exports.

Upload the EDA notebook first. Keep dataset ZIP + checksum privately; send the EDA report for review. Training cache V1 with a known preparation signature remains readable; new caches use V2. Never overwrite an existing run or source dataset.

Build both with `python -m scripts.generate_supsign_notebook`. Reusable code lives in `training/`; `scripts/` imports remain thin compatibility entry points. Old CNN/GTSRB, Kaggle and combined notebook artifacts are retained in Git history, not copied into an archive directory. Generic YOLO/VOC/COCO audit and local CLI remain available.
