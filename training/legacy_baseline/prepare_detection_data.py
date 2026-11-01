"""Convert existing GTSRB ROI annotations into a reproducible YOLO bootstrap dataset.

This is a pipeline baseline, not a Vietnamese full-scene detection benchmark.
"""
import argparse
import csv
import hashlib
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from PIL import Image
import yaml

from ai_engine.config import CLASS_MAPPING, PROJECT_ROOT

NAMES = [CLASS_MAPPING[i]["qcvn_code"] for i in range(10)]


def build_dataset(archive, csv_root, output, limit_per_class=None, roi_max_inclusive=False, deduplicate_overlaps=False):
    archive, csv_root, output = Path(archive).resolve(), Path(csv_root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Output already exists; choose a new directory to preserve the previous dataset")
    if limit_per_class is not None and limit_per_class < 1:
        raise ValueError("limit_per_class must be positive")
    rows_by_split, tracks, paths, hashes, overlaps = {}, {}, {}, {}, []
    for split in ("train", "val", "test"):
        with (csv_root / f"{split}.csv").open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        counts, selected = Counter(), []
        for row in rows:
            class_id = int(row["NewClassId"])
            if class_id not in CLASS_MAPPING or row["QCVN_Code"] != NAMES[class_id]:
                raise ValueError("CSV class ordering does not match the project taxonomy")
            path = (archive / row["Path"]).resolve()
            if not path.is_relative_to(archive) or not path.is_file():
                raise ValueError(f"Missing or unsafe source image: {row['Path']}")
            # Check all rows for train/val track leakage, even in a limited smoke subset.
            track = row.get("CompoundTrackId")
            if split in ("train", "val") and not track:
                raise ValueError("Train/val CSVs need CompoundTrackId to prevent track leakage")
            if track:
                if track in tracks and tracks[track] != split:
                    raise ValueError(f"Track leakage across splits: {track}")
                tracks[track] = split
            if path in paths:
                raise ValueError(f"Repeated image path: {row['Path']}")
            paths[path] = split
            if limit_per_class is not None and counts[class_id] >= limit_per_class:
                continue
            with Image.open(path) as image:
                width, height = image.size
                if (width, height) != (int(row["Width"]), int(row["Height"])):
                    raise ValueError(f"Image dimensions disagree with CSV: {row['Path']}")
                image.verify()
            x1, y1, x2, y2 = [int(row[key]) for key in ("Roi.X1", "Roi.Y1", "Roi.X2", "Roi.Y2")]
            if roi_max_inclusive:
                x2, y2 = x2 + 1, y2 + 1
            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                raise ValueError(f"Invalid ROI: {row['Path']}")
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            if checksum in hashes and hashes[checksum] != split:
                if not deduplicate_overlaps:
                    raise ValueError(f"Identical image content across splits: {row['Path']}; inspect data or pass --deduplicate-overlaps")
                overlaps.append({"sha256":checksum,"previous_split":hashes[checksum],"split":split,"source":row["Path"]})
            hashes[checksum] = split
            label = f"{class_id} {(x1+x2)/(2*width):.8f} {(y1+y2)/(2*height):.8f} {(x2-x1)/width:.8f} {(y2-y1)/height:.8f}\n"
            selected.append((path, row, checksum, label))
            counts[class_id] += 1
        if set(counts) != set(range(10)):
            raise ValueError(f"{split} must contain all 10 classes")
        rows_by_split[split] = selected
    dropped = []
    if deduplicate_overlaps:
        # Preserve the independent test set. Remove its exact copies from val/train,
        # and val's exact copies from train. Never modify original CSVs or images.
        for split, selected in rows_by_split.items():
            retained = []
            for entry in selected:
                if hashes[entry[2]] != split:
                    dropped.append({"source":entry[1]["Path"],"split":split,"sha256":entry[2]})
                else:
                    retained.append(entry)
            if {int(entry[1]["NewClassId"]) for entry in retained} != set(range(10)):
                raise ValueError(f"Deduplication leaves {split} without examples of every class")
            rows_by_split[split] = retained
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".yolo-build-", dir=output.parent))
    try:
        manifest = {"kind": "gtsrb_roi_bootstrap", "domain_limit": "Cropped German signs with ROI; not full-scene Vietnamese road data",
                    "roi_max": "inclusive" if roi_max_inclusive else "exclusive (matches existing CNN crop pipeline)",
                    "limit_per_class": limit_per_class, "names": NAMES, "splits": {},
                    "deduplication": {"enabled":deduplicate_overlaps,"priority":"test > val > train", "overlaps":overlaps,"dropped":dropped}}
        for split, rows in rows_by_split.items():
            image_dir, label_dir = staging / "images" / split, staging / "labels" / split
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            entries = []
            for index, (source, row, checksum, label) in enumerate(rows):
                filename = f"{index:06d}_{source.stem}{source.suffix.lower()}"
                shutil.copyfile(source, image_dir / filename)
                (label_dir / Path(filename).with_suffix(".txt")).write_text(label, encoding="utf-8")
                entries.append({"file": filename, "source": row["Path"], "sha256": checksum,
                                "class_id": int(row["NewClassId"]), "track": row.get("CompoundTrackId"), "label": label.strip()})
            manifest["splits"][split] = entries
        (staging / "data.yaml").write_text(yaml.safe_dump(
            {"path": str(output), "train": "images/train", "val": "images/val", "test": "images/test", "names": dict(enumerate(NAMES))},
            allow_unicode=True, sort_keys=False), encoding="utf-8")
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.rename(output)
    except Exception:
        shutil.rmtree(staging)
        raise
    return {split: len(rows) for split, rows in rows_by_split.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path(PROJECT_ROOT) / "archive")
    parser.add_argument("--csv-root", type=Path, default=Path(PROJECT_ROOT) / "data/processed")
    parser.add_argument("--output", type=Path, default=Path(PROJECT_ROOT) / "data/yolo_bootstrap")
    parser.add_argument("--limit-per-class", type=int)
    parser.add_argument("--roi-max-inclusive", action="store_true", help="Treat CSV ROI.X2/Y2 as inclusive; default matches existing crop code")
    parser.add_argument("--deduplicate-overlaps", action="store_true", help="Remove exact cross-split copies from train/val, preserve test, record exclusions")
    args = parser.parse_args()
    try:
        print(json.dumps(build_dataset(args.archive, args.csv_root, args.output, args.limit_per_class, args.roi_max_inclusive, args.deduplicate_overlaps), indent=2))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Dataset preparation failed: {error}\n")


if __name__ == "__main__":
    main()
