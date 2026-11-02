# Supported notebooks

1. SignSight_SupSign_EDA_Colab.ipynb — CPU; gdown, source audit, CAR35 preparation, report ZIP and optional prepared-cache download.
2. SignSight_SupSign_YOLO11s_Train_Colab.ipynb — GPU; gdown restores reviewed cache without resplitting, fine-tunes YOLO11s, validates and exports.

Both notebooks use local `/content` storage and gdown ZIP links only for dataset transfer: no Drive mount or automatic account storage. Download outputs before deleting the runtime. EDA defaults to downloading its report plus the prepared dataset ZIP and checksum; set DOWNLOAD_PREPARED_CACHE=False only when the cache is already safely retained. A new account/runtime must receive the cache via a gdown-compatible link and checksum. Resume requires the original run files still present; restoring run backups is not automatic.

Upload the EDA notebook first. Keep dataset ZIP + checksum privately; send the EDA report for review. Training cache V1 with a known preparation signature remains readable; new caches use V2. Never overwrite an existing run or source dataset.

EDA now exports an offline grouping review. Extract the report ZIP and open the root `index.html` to follow the current grouping report: inspect split concentration, contact sheets of the 12 largest groups, direct filename/dHash/capture joins, and per-class group support. CSVs include all groups/members and a spanning forest of joining edges. The review does not change labels or splits; replay agreement does not establish independent trips. It decodes cached images on CPU for dHash without re-auditing the raw ZIP. Re-running the grouping cell preserves the old report; the root index/handoff identify the current timestamped folder.

The global dHash section samples up to 12 joining pairs across all groups/distances, even outside the largest-group preview window. `dhash_edges.csv` exports all dHash forest edges. Per-group preview slots first cover available reasons so filename collisions cannot crowd out dHash.

The embedded pipeline refreshes its own imported module set on rerun and uses a source-hash directory to avoid stale Python/bytecode imports. Pipeline/grouping/export print the same pipeline ID. The report handoff stores that ID and the exact current grouping link; open `index.html` at the ZIP root to follow it. Export rejects missing dHash evidence, a different pipeline ID or a changed manifest. Earlier grouping folders are retained but are not the current report entry point.

Build both with `python -m scripts.generate_supsign_notebook`. Reusable code lives in `training/`; `scripts/` imports remain thin compatibility entry points. Old CNN/GTSRB, Kaggle and combined notebook artifacts are retained in Git history, not copied into an archive directory. Generic YOLO/VOC/COCO audit and local CLI remain available.
