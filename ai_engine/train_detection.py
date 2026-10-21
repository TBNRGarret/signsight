"""Train/evaluate YOLO with dataset validation, fixed taxonomy and recorded provenance."""
import argparse
import hashlib
import json
import math
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml
from PIL import Image

from ai_engine.config import PROJECT_ROOT
from ai_engine.detection import checkpoint_hash, configure_ultralytics
from ai_engine.prepare_detection_data import NAMES


def validate_dataset(data):
    data = Path(data).resolve()
    config = yaml.safe_load(data.read_text(encoding="utf-8"))
    names = config.get("names")
    if isinstance(names, dict):
        if set(names) != set(range(10)):
            raise ValueError("data.yaml must define exactly 10 indexed names")
        names = [names.get(i) for i in range(10)]
    if names != NAMES:
        raise ValueError("data.yaml must use the exact 10 project names in order")
    root = Path(config.get("path", data.parent))
    root = (data.parent / root).resolve() if not root.is_absolute() else root.resolve()
    checksum = hashlib.sha256(data.read_bytes())
    splits, seen_paths, seen_hashes = {}, set(), {}
    for split in ("train", "val", "test"):
        value = config.get(split)
        if not isinstance(value, str):
            raise ValueError("Each split must point to an images directory (including independent test)")
        directory = (root / value).resolve()
        if not directory.is_relative_to(root) or directory.parent.name != "images":
            raise ValueError("Split paths must stay under dataset root, using images/<split> layout")
        images = sorted(path for path in directory.rglob("*") if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
        if not images:
            raise ValueError(f"Empty image split: {split}")
        instances, classes = 0, set()
        for image in images:
            resolved = image.resolve()
            if not resolved.is_relative_to(root) or resolved in seen_paths:
                raise ValueError("Unsafe or repeated image path across splits")
            seen_paths.add(resolved)
            content_hash = hashlib.sha256(image.read_bytes()).hexdigest()
            if content_hash in seen_hashes and seen_hashes[content_hash] != split:
                raise ValueError("Identical image content across train/val/test")
            seen_hashes[content_hash] = split
            label = root / "labels" / directory.name / image.relative_to(directory).with_suffix(".txt")
            if not label.resolve().is_relative_to(root) or not label.is_file():
                raise ValueError(f"Missing label (use empty file for a verified negative): {label}")
            text = label.read_text(encoding="utf-8")
            for line in text.splitlines():
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) != 5:
                    raise ValueError(f"Expected class x_center y_center width height: {label}")
                class_id = int(parts[0])
                x, y, w, h = map(float, parts[1:])
                if class_id not in range(10) or not all(math.isfinite(n) for n in (x,y,w,h)) or not (0 < w <= 1 and 0 < h <= 1):
                    raise ValueError(f"Invalid YOLO label: {label}")
                if x-w/2 < -1e-6 or y-h/2 < -1e-6 or x+w/2 > 1+1e-6 or y+h/2 > 1+1e-6:
                    raise ValueError(f"Box exceeds image bounds: {label}")
                instances += 1
                classes.add(class_id)
            with Image.open(image) as source:
                if source.width * source.height > 40_000_000:
                    raise ValueError(f"Image too large: {image}")
                source.verify()
            checksum.update(f"{split}:{image.relative_to(root)}:{content_hash}:{text}".encode())
        if classes != set(range(10)):
            raise ValueError(f"{split} must include annotated examples of all 10 classes")
        splits[split] = {"images": len(images), "instances": instances}
        print(f"Validated {split}: {len(images)} images, {instances} boxes", flush=True)
    manifest = root / "manifest.json"
    domain = json.loads(manifest.read_text(encoding="utf-8")).get("kind", "custom") if manifest.is_file() else "custom_full_scene_unverified"
    return {"yaml": str(data), "sha256": checksum.hexdigest(), "domain": domain, "splits": splits}


def metrics_report(metrics):
    # ap_class_index includes only classes with ground-truth instances; never invent per-class scores.
    box = metrics.box
    values = {int(class_id): {"precision": float(box.p[index]), "recall": float(box.r[index]),
                            "map50": float(box.ap50[index]), "map50_95": float(box.ap[index])}
              for index, class_id in enumerate(box.ap_class_index)}
    return {"precision": float(box.mp), "recall": float(box.mr), "map50": float(box.map50),
            "map50_95": float(box.map), "per_class": {name: values.get(i) for i, name in enumerate(NAMES)}}


def activate(weights, destination):
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Never destroy the previous checkpoint. Stage the new file before replacing.
    if destination.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        shutil.copy2(destination, destination.with_name(f"best.{stamp}.pt"))
    staging = destination.with_suffix(".pt.pending")
    shutil.copy2(weights, staging)
    os.replace(staging, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("train", "evaluate", "validate"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", help="Local checkpoint, or Ultralytics model architecture such as yolo11n.yaml")
    parser.add_argument("--allow-download", action="store_true", help="Allow Ultralytics to download official starting weights")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=0, help="0 is the safe Windows default")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true", help="Mark a pipeline check; cannot activate its checkpoint")
    parser.add_argument("--activate", action="store_true", help="Copy a trained detector to the API checkpoint location")
    args = parser.parse_args()
    if args.command == "validate":
        try:
            print(json.dumps(validate_dataset(args.data), indent=2, ensure_ascii=False))
            return
        except (ValueError, OSError, KeyError, TypeError) as error:
            parser.exit(1, f"Dataset validation failed: {error}\n")
    if args.model is None or args.output is None:
        parser.error("Train/evaluate require --model and --output")
    if args.activate and (args.smoke or args.command != "train"):
        parser.error("Only a non-smoke training run can activate weights")
    if args.epochs < 1 or args.imgsz < 32 or args.batch < 1 or args.workers < 0:
        parser.error("Invalid training dimensions or counts")
    if args.output.exists():
        parser.error("Output exists; select a new run directory")
    if args.model.lower().endswith(".pt") and not Path(args.model).is_file() and not args.allow_download:
        parser.error("Checkpoint missing; supply a local file or explicitly pass --allow-download")
    if args.command == "evaluate" and not Path(args.model).is_file():
        parser.error("Evaluation requires a local trained checkpoint")
    try:
        dataset = validate_dataset(args.data)
        configure_ultralytics()
        from ultralytics import YOLO, __version__
        import torch
        model = YOLO(args.model, task="detect")
        output = args.output.resolve()
        if args.command == "train":
            model.train(data=str(args.data.resolve()), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                        device=args.device, workers=args.workers, seed=args.seed, deterministic=True,
                        fliplr=0.0, flipud=0.0, degrees=5.0, project=str(output.parent), name=output.name,
                        exist_ok=False, plots=True, amp=False, pretrained=not args.model.endswith(".yaml"))
            weights = Path(model.trainer.best)
            model = YOLO(str(weights), task="detect")
        else:
            output.mkdir(parents=True)
            weights = Path(args.model).resolve()
        ordered_names = [model.names[i] for i in range(len(model.names))]
        if ordered_names != NAMES or model.task != "detect":
            raise ValueError("Trained checkpoint taxonomy does not match SignSight")
        evaluations = {}
        for split in ("val", "test"):
            metrics = model.val(data=str(args.data.resolve()), split=split, imgsz=args.imgsz, batch=args.batch,
                                device=args.device, workers=args.workers, plots=True,
                                project=str(output), name=f"evaluate_{split}", exist_ok=False)
            evaluations[split] = metrics_report(metrics)
        report = {"created_at": datetime.now(timezone.utc).isoformat(), "smoke": args.smoke,
                  "dataset": dataset, "weights": str(weights), "model_version": checkpoint_hash(weights),
                  "ultralytics": __version__, "torch": torch.__version__, "settings": {key: str(value) if isinstance(value, Path) else value for key,value in vars(args).items()},
                  "metrics": evaluations,
                  "limitation": "GTSRB ROI results measure bootstrap detection; Vietnamese full-scene quality needs an independent road-scene dataset" if dataset["domain"] == "gtsrb_roi_bootstrap" else "Verify independent scene/session splits and deployment domain before accepting metrics"}
        (output / "detection_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        if args.activate:
            activate(weights, Path(PROJECT_ROOT) / "ai_engine/checkpoints/detection/best.pt")
        print(f"Report: {output / 'detection_report.json'}")
    except (ValueError, OSError, ImportError) as error:
        parser.exit(1, f"Detection pipeline failed: {error}\n")


if __name__ == "__main__":
    main()
