"""Optional YOLO detector. Missing/incompatible weights never fall back to CNN."""

import hashlib
import math
import os
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from ai_engine.config import CLASS_MAPPING, PROJECT_ROOT
from ai_engine.catalog import DEFAULT_CATALOG, ModelClassMapping


class DetectorUnavailable(RuntimeError):
    pass


@dataclass
class Prediction:
    predicted_class: int
    confidence: float
    bbox: tuple[float, float, float, float] | None
    model_class_id: int | None = None


@dataclass
class DetectionResult:
    model_version: str
    predictions: list[Prediction]
    mapping_sha256: str | None = None
    catalog_sha256: str | None = None


def checkpoint_hash(path: Path) -> str:
    path = Path(path)
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return "sha256:" + checksum.hexdigest()


def configure_ultralytics():
    config_dir = os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(PROJECT_ROOT) / ".cache" / "ultralytics"))
    Path(config_dir).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")


class YoloDetector:
    def __init__(self, weights: Path, device: str | None = None, confidence: float = 0.25,
                 *, catalog=None, mapping_path=None):
        if not math.isfinite(confidence) or not 0 < confidence <= 1:
            raise ValueError("YOLO confidence must be finite and greater than 0, up to 1")
        self.weights = Path(weights)
        self.device = device
        self.confidence = confidence
        self.catalog = catalog or DEFAULT_CATALOG
        self.mapping_path = Path(mapping_path) if mapping_path is not None else None
        self._mapping = None
        self._lock = Lock()
        self._model = None
        self._signature = None
        self._version = None
        self._reason = "weights_missing"

    def _load(self):
        if not self.weights.is_file():
            self._model = None
            self._reason = "weights_missing"
            raise DetectorUnavailable("YOLO checkpoint is not configured")
        mapping_bytes = None
        if self.mapping_path is not None:
            try:
                if self.mapping_path.stat().st_size > 1024*1024: raise ValueError('Mapping too large')
                mapping_bytes = self.mapping_path.read_bytes()
            except (OSError,ValueError):
                self._model = None; self._reason = 'mapping_invalid'
                raise DetectorUnavailable('YOLO model mapping is missing or invalid') from None
        signature = (self.weights.stat().st_mtime_ns, self.weights.stat().st_size,
                     hashlib.sha256(mapping_bytes).hexdigest() if mapping_bytes is not None else None)
        if self._model is not None and signature == self._signature:
            return
        configure_ultralytics()
        try:
            from ultralytics import YOLO
        except ImportError:
            self._reason = "dependencies_missing"
            raise DetectorUnavailable("Install ai_engine/requirements-yolo.txt to use YOLO") from None
        try:
            mapping = None
            if mapping_bytes is not None:
                try: mapping = ModelClassMapping(json.loads(mapping_bytes),self.catalog,self.weights)
                except (ValueError,TypeError,KeyError):
                    self._reason = 'mapping_invalid'
                    raise DetectorUnavailable('YOLO mapping must be reviewed and match this checkpoint/catalog') from None
            model = YOLO(str(self.weights), task="detect")
            names = model.names
            names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
            expected = mapping.names if mapping else [CLASS_MAPPING[i]["qcvn_code"] for i in range(10)]
            if model.task != "detect" or names != expected:
                self._reason = "taxonomy_mismatch"
                raise DetectorUnavailable("YOLO checkpoint taxonomy must match the configured reviewed mapping or legacy taxonomy")
            version = checkpoint_hash(self.weights)
        except DetectorUnavailable:
            self._model = None
            raise
        except Exception:
            self._model = None
            self._reason = "invalid_checkpoint"
            raise DetectorUnavailable("YOLO checkpoint could not be loaded") from None
        self._model, self._version, self._signature = model, version, signature
        self._mapping = mapping
        self._reason = None

    def status(self):
        with self._lock:
            try:
                self._load()
            except DetectorUnavailable:
                return {"ready": False, "reason": self._reason, "model_version": None,
                        "confidence_threshold": self.confidence}
            return {"ready": True, "reason": None, "model_version": self._version,
                    "confidence_threshold": self.confidence,
                    'mapping_sha256': self._mapping.sha256 if self._mapping else None,
                    'catalog_sha256': self.catalog.sha256}

    def predict(self, image) -> DetectionResult:
        with self._lock:
            self._load()
            try:
                results = self._model.predict(source=image, conf=self.confidence, iou=0.45, max_det=25,
                                              device=self.device, save=False, verbose=False)
            except Exception:
                raise DetectorUnavailable("YOLO inference failed; check the configured device and checkpoint") from None
            predictions = []
            for result in results:
                if result.boxes is None:
                    continue
                for coords, score, class_id in zip(result.boxes.xyxy.cpu().tolist(),
                                                   result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
                    maximum = len(self._mapping.targets) if self._mapping else len(CLASS_MAPPING)
                    if not math.isfinite(class_id) or class_id != int(class_id) or not 0 <= int(class_id) < maximum:
                        raise DetectorUnavailable("Detector returned an unsupported class")
                    if not math.isfinite(score) or not 0 <= score <= 1 or not all(math.isfinite(value) for value in coords):
                        raise DetectorUnavailable("Detector returned invalid coordinates or confidence")
                    x1, y1, x2, y2 = coords
                    box = (max(0.0, min(x1, image.width)), max(0.0, min(y1, image.height)),
                           max(0.0, min(x2, image.width)), max(0.0, min(y2, image.height)))
                    if box[2] <= box[0] or box[3] <= box[1]:
                        raise DetectorUnavailable("Detector returned an empty bounding box")
                    raw_id = int(class_id)
                    catalog_id = self._mapping.catalog_id(raw_id) if self._mapping else raw_id
                    predictions.append(Prediction(catalog_id, float(score), box, raw_id))
            return DetectionResult(self._version, predictions,
                                   self._mapping.sha256 if self._mapping else None,self.catalog.sha256)
