# Prepare a CAR35 dataset from downloaded YOLO folders

Use this workflow for a downloaded `data.yaml` with `train/images`, `train/labels`, `valid/images`, `valid/labels`, `test/images` and `test/labels`. It reads exactly these roots, preserving the original files. It does not recursively audit other images, databases or uploads in the source workspace.

From the application checkout, with the existing Python training dependencies installed:

```python
from pathlib import Path
from training.data.folder_dataset import prepare_folder_dataset, verify_folder_dataset

source = Path("..").resolve()  # Directory containing the downloaded data.yaml
output = source / "data/vietnam_yolo/car35_v4"
manifest = prepare_folder_dataset(source, output, workers=8)
summary = verify_folder_dataset(output)
print(summary)
```

Choose a new output directory each time. Existing directories and paths overlapping the consumed source roots are rejected.

The output contains:

```text
car35_v4/
  data.yaml
  manifest.json
  class_counts.csv
  images/
    train/
    val/
    test/
  labels/
    train/
    val/
    test/
```

`CAR35` retains the existing model's ordered 35 class names with IDs 0–34. The original 107-class IDs are remapped by name, with every selected bbox retained. Invalid or missing annotations are excluded. Exact-byte image duplicates are removed only when all source labels agree, including labels outside CAR35; contradictory duplicate annotations are quarantined. Verified source backgrounds and images containing only classes outside CAR35 remain negative examples for the selected taxonomy. A negative example may still contain traffic signs outside the chosen 35 classes.

Images with dHash distance at most 4 are joined into connected components. Each component stays entirely in one split. Numeric filenames do not establish capture groups. The seeded splitter targets 70% train, 15% validation and 15% test. It reserves each class's strongest group in train, then balances image and per-class box ratios while seeking holdout coverage. This prevents most of a rare class going to validation while only one or two boxes remain for learning. Actual ratios and class counts must be read from the output. A class confined to one group remains in train and is reported as missing from holdouts; images are never copied between splits to hide that gap. A dominant group can make proportional coverage impossible; a tiny holdout count is not adequate evidence of accuracy even if that class is technically present.

The manifest records source aliases, SHA-256 for every copied image and generated label, class counts, exclusions, grouping settings and implementation-file hashes. The verifier checks file inventories, hashes, label geometry, class counts and that recorded groups/hashes do not cross splits. This is an integrity check, not a visual audit proving every dHash link is meaningful or every visually similar pair was found.

This is a new **development benchmark**, not an independent car-view field test. Compare future configurations on this fixed version, and reserve a separately collected car-view dataset for field claims. Metrics from the old V3 split are not directly comparable with the rebuilt split.

The exported `data.yaml` omits an explicit `path`, so Ultralytics resolves images beside the YAML after moving or extracting the folder. Pass an absolute YAML filename when training:

```python
from pathlib import Path
from ultralytics import YOLO

data = Path("../data/vietnam_yolo/car35_v4/data.yaml").resolve()
model = YOLO("yolo11s.pt")
model.train(
    data=str(data), epochs=80, imgsz=640, batch=8,
    seed=42, deterministic=True, cache=False, patience=20,
    fliplr=0.0, flipud=0.0, degrees=0.0, shear=0.0,
    perspective=0.0, mixup=0.0, mosaic=0.5, close_mosaic=10,
    project="runs/car35_v4", name="yolo11s_640", exist_ok=False,
)
```

Treat that as a starting configuration; this preparation task does not launch training or replace the serving checkpoint. Choose settings with validation, then evaluate the test split after the settings are frozen.

Start the V4 benchmark from the official pretrained `yolo11s.pt` as shown above. Earlier SupSign checkpoints may have trained on images now assigned to the V4 holdout; evaluating those existing weights on V4 is a diagnostic and cannot establish an unbiased new test result.

For Colab, archive the entire generated folder, share/download it with gdown, and extract it to local `/content`. Point training at its `data.yaml`. No Drive mount is needed. This folder is a standard YOLO dataset, **not** a V3 prepared-cache artifact: do not supply it to the existing V3 notebook's `restore_dataset` cell. Its manifest intentionally uses a distinct schema and does not masquerade as a legacy cache.
