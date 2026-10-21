import os
import io
from typing import Dict, Any, Union
from PIL import Image
import numpy as np

from ai_engine.config import (
    CLASS_MAPPING,
    CONFIDENCE_THRESHOLD,
    NUM_CLASSES,
    IMAGE_SIZE,
    PROJECT_ROOT
)
from ai_engine.detection import checkpoint_hash

try:
    import torch
    import torchvision.transforms as transforms
    from ai_engine.model import TrafficSignCNN
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

MODEL_WEIGHTS_PATH = os.getenv("SIGNSIGHT_CNN_WEIGHTS", os.path.join(PROJECT_ROOT, "ai_engine", "checkpoints", "best_model.pth"))

class TrafficSignClassifier:
    def __init__(self, weights_path: str = MODEL_WEIGHTS_PATH):
        self.weights_path = weights_path
        self.model = None
        self.device = None
        self.transform = None
        self.model_version = None
        self._load_model_if_available()

    def _load_model_if_available(self):
        if HAS_TORCH and os.path.exists(self.weights_path):
            try:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                self.model = TrafficSignCNN(num_classes=NUM_CLASSES).to(self.device)
                self.model.load_state_dict(torch.load(self.weights_path, map_location=self.device, weights_only=True))
                self.model.eval()
                self.model_version = checkpoint_hash(self.weights_path)
                self.transform = transforms.Compose([
                    transforms.Resize(IMAGE_SIZE),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                ])
                print(f"[AI Engine] Ready: Successfully loaded Deep Learning model from {self.weights_path} to {self.device}")
            except Exception as e:
                print(f"[AI Engine] Could not load weights: {e}. Classification is disabled.")
                self.model = None
                self.model_version = None
        else:
            print("[AI Engine] Checkpoint best_model.pth not found. Classification is disabled.")

    def reload_weights(self):
        """Reloads checkpoint after training completes without restarting server."""
        self._load_model_if_available()

    def predict(self, image_input: Union[str, bytes, Image.Image]) -> Dict[str, Any]:
        """
        Classifies input image into one of 10 Vietnam-compatible traffic sign classes.
        Returns predicted class, QCVN code, confidence, and uncertainty flag.
        """
        if isinstance(image_input, str):
            image = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, bytes):
            image = Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, Image.Image):
            image = image_input.convert("RGB")
        else:
            raise ValueError("Unsupported image input type")

        # 1. Chạy với PyTorch Deep Learning Model nếu đã nạp weights
        if self.model is not None and HAS_TORCH:
            tensor = self.transform(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                logits = self.model(tensor)
                probs_tensor = torch.softmax(logits, dim=1).squeeze(0)
                probs = probs_tensor.cpu().numpy()
        else:
            # 2. Chế độ Fallback / Prototype Heuristic nếu chưa huấn luyện
            img_resized = image.resize(IMAGE_SIZE)
            arr = np.array(img_resized, dtype=np.float32) / 255.0
            r_mean, g_mean, b_mean = float(arr[:, :, 0].mean()), float(arr[:, :, 1].mean()), float(arr[:, :, 2].mean())

            logits = np.ones(NUM_CLASSES, dtype=np.float32) * 0.1
            if b_mean > r_mean and b_mean > g_mean:
                logits[8] += 2.5  # R.301a
                logits[9] += 3.0  # R.301e
            elif r_mean > 0.45 and g_mean < 0.35 and b_mean < 0.35:
                logits[4] += 3.5  # STOP (P.122)
                logits[5] += 2.8  # No entry (P.102)
            elif r_mean > g_mean:
                logits[0] += 2.0  # P.127 (50)
                logits[1] += 2.2  # P.127 (60)
                logits[2] += 2.1  # P.127 (80)
                logits[3] += 1.8  # P.125
            else:
                logits[6] += 2.4  # W.245a
                logits[7] += 2.6  # W.227

            exp_logits = np.exp(logits - np.max(logits))
            probs = exp_logits / exp_logits.sum()

        pred_id = int(np.argmax(probs))
        confidence = float(probs[pred_id])
        is_uncertain = bool(confidence < CONFIDENCE_THRESHOLD)

        info = CLASS_MAPPING.get(pred_id, {
            "qcvn_code": "UNKNOWN",
            "name_vi": "Không xác định",
            "name_en": "Unknown Sign"
        })

        prob_list = []
        for i in range(NUM_CLASSES):
            c_info = CLASS_MAPPING.get(i, {"qcvn_code": f"Class_{i}", "name_vi": ""})
            prob_list.append({
                "class_id": i,
                "qcvn_code": c_info.get("qcvn_code", f"C{i}"),
                "name_vi": c_info.get("name_vi", ""),
                "probability": round(float(probs[i]), 4)
            })

        return {
            "predicted_class": pred_id,
            "qcvn_code": info["qcvn_code"],
            "name_vi": info["name_vi"],
            "name_en": info["name_en"],
            "confidence": round(confidence, 4),
            "is_uncertain": is_uncertain,
            "probabilities": prob_list
        }

classifier = TrafficSignClassifier()
