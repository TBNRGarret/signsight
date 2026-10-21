"""Optional YOLO detector. Missing/incompatible weights never fall back to CNN."""

import hashlib
import math
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from ai_engine.config import CLASS_MAPPING, PROJECT_ROOT


class DetectorUnavailable(RuntimeError):
    pass


@dataclass
class Prediction:
    predicted_class: int
    confidence: float
    bbox: tuple[float, float, float, float] | None


@dataclass
class DetectionResult:
    model_version: str
    predictions: list[Prediction]


def checkpoint_hash(path: Path) -> str:
    path = Path(path)
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return "sha256:" + checksum.hexdigest()


def configure_ultralytics():
    os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(PROJECT_ROOT) / ".cache" / "ultralytics"))
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")


class YoloDetector:
    def __init__(self, weights: Path, device: str | None = None, confidence: float = 0.25):
        if not math.isfinite(confidence) or not 0 < confidence <= 1:
            raise ValueError("YOLO confidence must be finite and greater than 0, up to 1")
        self.weights = Path(weights)
        self.device = device
        self.confidence = confidence
        self._lock = Lock()
        self._model = None
        self._signature = None
        self._version = None
        self._reason = "weights_missing"

    def _load(self):
        if not self.weights.is_file():
            self._model = None
            self._reason = "weights_missing"
            raise DetectorUnavailable("YOLO checkpoint is not configured; train a 10-class detector first")
        signature = (self.weights.stat().st_mtime_ns, self.weights.stat().st_size)
        if self._model is not None and signature == self._signature:
            return
        configure_ultralytics()
        try:
            from ultralytics import YOLO
        except ImportError:
            self._reason = "dependencies_missing"
            raise DetectorUnavailable("Install ai_engine/requirements-yolo.txt to use YOLO") from None
        try:
            model = YOLO(str(self.weights), task="detect")
            names = model.names
            names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
            expected = [CLASS_MAPPING[i]["qcvn_code"] for i in range(10)]
            if model.task != "detect" or names != expected:
                self._reason = "taxonomy_mismatch"
                raise DetectorUnavailable("YOLO checkpoint must use the project's exact 10-class taxonomy")
            version = checkpoint_hash(self.weights)
        except DetectorUnavailable:
            self._model = None
            raise
        except Exception:
            self._model = None
            self._reason = "invalid_checkpoint"
            raise DetectorUnavailable("YOLO checkpoint could not be loaded") from None
        self._model, self._version, self._signature = model, version, signature
        self._reason = None

    def status(self):
        with self._lock:
            try:
                self._load()
            except DetectorUnavailable:
                return {"ready": False, "reason": self._reason, "model_version": None,
                        "confidence_threshold": self.confidence}
            return {"ready": True, "reason": None, "model_version": self._version,
                    "confidence_threshold": self.confidence}

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
                    if not math.isfinite(class_id) or class_id != int(class_id) or int(class_id) not in CLASS_MAPPING:
                        raise DetectorUnavailable("Detector returned an unsupported class")
                    if not math.isfinite(score) or not 0 <= score <= 1 or not all(math.isfinite(value) for value in coords):
                        raise DetectorUnavailable("Detector returned invalid coordinates or confidence")
                    x1, y1, x2, y2 = coords
                    box = (max(0.0, min(x1, image.width)), max(0.0, min(y1, image.height)),
                           max(0.0, min(x2, image.width)), max(0.0, min(y2, image.height)))
                    if box[2] <= box[0] or box[3] <= box[1]:
                        raise DetectorUnavailable("Detector returned an empty bounding box")
                    predictions.append(Prediction(int(class_id), float(score), box))
            return DetectionResult(self._version, predictions)
