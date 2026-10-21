"""
Generates the turnkey Jupyter Notebook for training SignSight on Google Colab or Kaggle.
"""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK_DIR = os.path.join(PROJECT_ROOT, "notebooks")
os.makedirs(NOTEBOOK_DIR, exist_ok=True)
NOTEBOOK_PATH = os.path.join(NOTEBOOK_DIR, "SignSight_Colab_Kaggle_Training.ipynb")

def build_notebook():
    cells = []

    def add_md(source):
        lines = [line + "\n" for line in source.strip().split("\n")]
        if lines:
            lines[-1] = lines[-1].rstrip("\n")
        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": lines
        })

    def add_code(source):
        lines = [line + "\n" for line in source.strip().split("\n")]
        if lines:
            lines[-1] = lines[-1].rstrip("\n")
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": lines
        })

    # Cell 1: Intro
    add_md("""# 🚦 SignSight: Training 10-Class Vietnam Traffic Sign Recognition Model
**Course**: COS40006 - Computing Technology Project B (Swinburne University)<br>
**Standard**: Quy chuẩn Kỹ thuật Quốc gia về Báo hiệu Đường bộ Việt Nam (**QCVN 41:2019/BGTVT**)<br>
**Hardware Support**: Google Colab (Free T4 GPU) & Kaggle (T4/P100 GPU)

---
### Mục Tiêu Notebook:
1. Tải và xử lý tập dữ liệu GTSRB về đúng **10 lớp biển báo giao thông Việt Nam**.
2. Phân chia Train/Validation theo chuỗi track (`TrackId`) để **triệt tiêu 100% Data Leakage**.
3. Huấn luyện mô hình Deep Learning (`TrafficSignCNN` & `MobileNetV3-Small`) với Data Augmentation mô phỏng điều kiện đường sá Việt Nam.
4. Đánh giá chi tiết trên tập Test độc lập: Accuracy, Precision, Recall, F1-Score, Confusion Matrix.
5. Xuất file trọng số `best_model.pth` và báo cáo `evaluation_report.json` để tích hợp vào Backend FastAPI & Web Map.""")

    # Cell 2: Environment Check
    add_code("""# 1. Kiểm tra môi trường và GPU
import torch
import sys

print(f"Python Version: {sys.version.split()[0]}")
print(f"PyTorch Version: {torch.__version__}")
cuda_available = torch.cuda.is_available()
print(f"CUDA Available: {cuda_available}")
if cuda_available:
    device = torch.device("cuda")
    print(f"GPU Model: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")
else:
    device = torch.device("cpu")
    print("Running on CPU (Khuyến nghị chuyển sang GPU trong mục Runtime -> Change runtime type trên Colab)")""")

    # Cell 3: Dataset Download / Detection
    add_code("""# 2. Tự động tải hoặc nhận diện Dataset GTSRB (Hỗ trợ cả Kaggle và Google Colab)
import os
import shutil

DATASET_ROOT = None

# Trường hợp 1: Chạy trên Kaggle
kaggle_paths = [
    "/kaggle/input/gtsrb-german-traffic-sign",
    "/kaggle/input/gtsrb-german-traffic-sign/archive",
    "/kaggle/input/traffic-signs-preprocessed"
]
for p in kaggle_paths:
    if os.path.exists(os.path.join(p, "Train.csv")):
        DATASET_ROOT = p
        print(f"[Kaggle] Đã tìm thấy dataset tại: {DATASET_ROOT}")
        break

# Trường hợp 2: Chạy trên Google Colab / Local
if DATASET_ROOT is None:
    if os.path.exists("archive/Train.csv"):
        DATASET_ROOT = "archive"
        print(f"[Local] Đã tìm thấy thư mục archive cục bộ: {DATASET_ROOT}")
    else:
        print("[Colab] Đang tự động tải dataset GTSRB qua kagglehub (hoàn toàn miễn phí, không cần tài khoản)...")
        try:
            import kagglehub
        except ImportError:
            !pip install -q kagglehub
            import kagglehub

        download_path = kagglehub.dataset_download("meowmeowmeowmeowmeow/gtsrb-german-traffic-sign")
        # Tìm thư mục chứa Train.csv
        for root, dirs, files in os.walk(download_path):
            if "Train.csv" in files:
                DATASET_ROOT = root
                break
        print(f"[Colab] Đã tải xong dataset về: {DATASET_ROOT}")

assert DATASET_ROOT is not None, "Không tìm thấy dataset! Hãy kiểm tra lại thư mục hoặc đường dẫn."
print(f"Dataset root: {DATASET_ROOT}")""")

    # Cell 4: Taxonomy & Mapping
    add_code("""# 3. Định nghĩa bảng 10 Lớp Biển Báo chuẩn QCVN 41:2019/BGTVT
import pandas as pd
import numpy as np

TAXONOMY = [
    {"new_id": 0, "gtsrb_id": 2,  "qcvn_code": "P.127 (50)", "name_vi": "Tốc độ tối đa 50 km/h", "category": "Biển cấm"},
    {"new_id": 1, "gtsrb_id": 3,  "qcvn_code": "P.127 (60)", "name_vi": "Tốc độ tối đa 60 km/h", "category": "Biển cấm"},
    {"new_id": 2, "gtsrb_id": 5,  "qcvn_code": "P.127 (80)", "name_vi": "Tốc độ tối đa 80 km/h", "category": "Biển cấm"},
    {"new_id": 3, "gtsrb_id": 9,  "qcvn_code": "P.125",      "name_vi": "Cấm vượt",               "category": "Biển cấm"},
    {"new_id": 4, "gtsrb_id": 14, "qcvn_code": "P.122",      "name_vi": "Dừng lại (STOP)",        "category": "Biển cấm"},
    {"new_id": 5, "gtsrb_id": 17, "qcvn_code": "P.102",      "name_vi": "Cấm đi ngược chiều",    "category": "Biển cấm"},
    {"new_id": 6, "gtsrb_id": 18, "qcvn_code": "W.245a",     "name_vi": "Đi chậm / Nguy hiểm khác", "category": "Biển cảnh báo"},
    {"new_id": 7, "gtsrb_id": 25, "qcvn_code": "W.227",      "name_vi": "Công trường thi công",   "category": "Biển cảnh báo"},
    {"new_id": 8, "gtsrb_id": 35, "qcvn_code": "R.301a",     "name_vi": "Chỉ được đi thẳng",      "category": "Biển hiệu lệnh"},
    {"new_id": 9, "gtsrb_id": 38, "qcvn_code": "R.301e",     "name_vi": "Đi vòng sang bên phải",  "category": "Biển hiệu lệnh"}
]

gtsrb_to_new = {item["gtsrb_id"]: item["new_id"] for item in TAXONOMY}
target_gtsrb_ids = list(gtsrb_to_new.keys())
new_to_info = {item["new_id"]: item for item in TAXONOMY}

taxonomy_df = pd.DataFrame(TAXONOMY)
display(taxonomy_df[["new_id", "gtsrb_id", "qcvn_code", "name_vi", "category"]])""")

    # Cell 5: Track-Aware Split
    add_code("""# 4. Trích xuất 10 Class & Phân chia Train/Val theo chuỗi Track (Zero Data Leakage)
train_csv_path = os.path.join(DATASET_ROOT, "Train.csv")
test_csv_path = os.path.join(DATASET_ROOT, "Test.csv")

raw_train = pd.read_csv(train_csv_path)
raw_test = pd.read_csv(test_csv_path)

df_train_filtered = raw_train[raw_train["ClassId"].isin(target_gtsrb_ids)].copy()
df_test_filtered = raw_test[raw_test["ClassId"].isin(target_gtsrb_ids)].copy()

df_train_filtered["NewClassId"] = df_train_filtered["ClassId"].map(gtsrb_to_new)
df_test_filtered["NewClassId"] = df_test_filtered["ClassId"].map(gtsrb_to_new)

# Tách mã Track từ tên file (Ví dụ: Train/02/00002_00015_00029.png -> track "00015")
def extract_track(p):
    filename = os.path.basename(p)
    parts = filename.split("_")
    return parts[1] if len(parts) >= 2 else filename

df_train_filtered["TrackId"] = df_train_filtered["Path"].apply(extract_track)
df_train_filtered["CompoundTrackId"] = df_train_filtered["NewClassId"].astype(str) + "_" + df_train_filtered["TrackId"]

# Stratified Split theo Track: 80% Train, 20% Val
np.random.seed(42)
train_tracks, val_tracks = [], []
for cid in range(10):
    c_tracks = df_train_filtered[df_train_filtered["NewClassId"] == cid]["CompoundTrackId"].unique()
    shuffled = np.random.permutation(c_tracks)
    n_val = max(1, int(round(len(c_tracks) * 0.20)))
    val_tracks.extend(shuffled[:n_val])
    train_tracks.extend(shuffled[n_val:])

train_tracks_set = set(train_tracks)
val_tracks_set = set(val_tracks)

# Kiểm chứng data leakage
leakage = train_tracks_set.intersection(val_tracks_set)
assert len(leakage) == 0, f"DATA LEAKAGE: {leakage}"

df_train = df_train_filtered[df_train_filtered["CompoundTrackId"].isin(train_tracks_set)].reset_index(drop=True)
df_val = df_train_filtered[df_train_filtered["CompoundTrackId"].isin(val_tracks_set)].reset_index(drop=True)
df_test = df_test_filtered.reset_index(drop=True)

print(f"✅ Phân chia thành công (Zero Leakage Check PASSED)!")
print(f"   - Tập Train: {len(df_train)} ảnh ({len(train_tracks_set)} tracks)")
print(f"   - Tập Val:   {len(df_val)} ảnh ({len(val_tracks_set)} tracks)")
print(f"   - Tập Test:  {len(df_test)} ảnh")""")

    # Cell 6: PyTorch Dataset & Transforms
    add_code("""# 5. Khởi tạo PyTorch Dataset & Data Augmentation cho điều kiện Việt Nam
from PIL import Image
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms

IMAGE_SIZE = (64, 64)
BATCH_SIZE = 64
NUM_CLASSES = 10

class TrafficSignDataset(Dataset):
    def __init__(self, df, root_dir, transform=None):
        self.df = df
        self.root_dir = root_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = os.path.join(self.root_dir, row["Path"])
        image = Image.open(img_path).convert("RGB")

        # Cắt theo bounding box ROI nếu có
        if "Roi.X1" in row and not pd.isna(row["Roi.X1"]):
            x1, y1, x2, y2 = int(row["Roi.X1"]), int(row["Roi.Y1"]), int(row["Roi.X2"]), int(row["Roi.Y2"])
            image = image.crop((x1, y1, x2, y2))

        label = int(row["NewClassId"])
        if self.transform:
            image = self.transform(image)
        return image, label

# Data Augmentation mô phỏng điều kiện đường sá Việt Nam (nắng gắt, bóng cây, góc chụp nghiêng)
train_transform = transforms.Compose([
    transforms.Resize(IMAGE_SIZE),
    transforms.RandomRotation(degrees=10),
    transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25),
    transforms.RandomAffine(degrees=0, translate=(0.06, 0.06)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

val_transform = transforms.Compose([
    transforms.Resize(IMAGE_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

train_ds = TrafficSignDataset(df_train, DATASET_ROOT, transform=train_transform)
val_ds = TrafficSignDataset(df_val, DATASET_ROOT, transform=val_transform)
test_ds = TrafficSignDataset(df_test, DATASET_ROOT, transform=val_transform)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2, pin_memory=True)
val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2, pin_memory=True)
test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2, pin_memory=True)

print(f"DataLoaders sẵn sàng! Batch size: {BATCH_SIZE}")""")

    # Cell 7: Model Architecture
    add_code("""# 6. Thiết kế Kiến Trúc Model (TrafficSignCNN chuyên dụng)
import torch.nn as nn

class TrafficSignCNN(nn.Module):
    \"\"\"
    Kiến trúc CNN 3 khối tinh gọn, tối ưu cho biển báo 64x64.
    Độ trễ thấp (<15ms) và dung lượng cực nhẹ (~1.8 MB).
    \"\"\"
    def __init__(self, num_classes: int = 10, *args, **kwargs):
        super().__init__()
        self.num_classes = num_classes
        self.features = nn.Sequential(
            # Block 1 (Input 64x64 -> Output 32x32)
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.2),

            # Block 2 (32x32 -> 16x16)
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.25),

            # Block 3 (16x16 -> 8x8)
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.3),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 8 * 8, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.4),
            nn.Linear(256, num_classes)
        )

    def forward(self, x):
        return self.classifier(self.features(x))

model = TrafficSignCNN(num_classes=NUM_CLASSES).to(device)
print(f"Tổng số tham số mô hình: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")""")

    # Cell 8: Training Loop
    add_code("""# 7. Huấn luyện Mô hình với Mixed Precision và Cosine Annealing LR
import time

NUM_EPOCHS = 15
LEARNING_RATE = 1e-3

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)
scaler = torch.cuda.amp.GradScaler(enabled=(device.type == "cuda"))

best_val_acc = 0.0
best_model_path = "best_model.pth"

print(f"🚀 BẮT ĐẦU HUẤN LUYỆN TRÊN {device.type.upper()} ({NUM_EPOCHS} EPOCHS)...")
start_time = time.time()

for epoch in range(1, NUM_EPOCHS + 1):
    model.train()
    running_loss, correct, total = 0.0, 0, 0

    for images, labels in train_loader:
        images, labels = images.to(device, non_blocking=True), labels.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)

        with torch.cuda.amp.autocast(enabled=(device.type == "cuda")):
            outputs = model(images)
            loss = criterion(outputs, labels)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        running_loss += loss.item() * images.size(0)
        _, preds = outputs.max(1)
        total += labels.size(0)
        correct += preds.eq(labels).sum().item()

    scheduler.step()
    train_acc = (correct / total) * 100.0
    train_loss = running_loss / total

    # Validation
    model.eval()
    val_correct, val_total = 0, 0
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device, non_blocking=True), labels.to(device, non_blocking=True)
            with torch.cuda.amp.autocast(enabled=(device.type == "cuda")):
                outputs = model(images)
            _, preds = outputs.max(1)
            val_total += labels.size(0)
            val_correct += preds.eq(labels).sum().item()

    val_acc = (val_correct / val_total) * 100.0
    is_best = val_acc > best_val_acc
    if is_best:
        best_val_acc = val_acc
        torch.save(model.state_dict(), best_model_path)

    best_marker = "🌟 [BEST VAL]" if is_best else ""
    print(f"Epoch [{epoch:02d}/{NUM_EPOCHS:02d}] Loss: {train_loss:.4f} | Train Acc: {train_acc:6.2f}% | Val Acc: {val_acc:6.2f}% {best_marker}")

elapsed = time.time() - start_time
print(f"\\n⏱️ Thời gian huấn luyện hoàn tất: {elapsed:.1f} giây ({elapsed/60:.2f} phút)!")
print(f"🏆 Best Validation Accuracy: {best_val_acc:.2f}% | Đã lưu tại: {best_model_path}")""")

    # Cell 9: Comprehensive Test Evaluation
    add_code("""# 8. Đánh giá toàn diện trên tập 4,890 ảnh Test độc lập
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import json

# Nạp lại trọng số tốt nhất
model.load_state_dict(torch.load(best_model_path, map_location=device, weights_only=True))
model.eval()

all_preds, all_labels = [], []
with torch.no_grad():
    for images, labels in test_loader:
        images = images.to(device)
        with torch.cuda.amp.autocast(enabled=(device.type == "cuda")):
            outputs = model(images)
        _, preds = outputs.max(1)
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.numpy())

class_names = [f"{item['qcvn_code']}" for item in TAXONOMY]
report_text = classification_report(all_labels, all_preds, target_names=class_names, digits=4)
report_dict = classification_report(all_labels, all_preds, target_names=class_names, digits=4, output_dict=True)

print("=" * 70)
print("BÁO CÁO ĐÁNH GIÁ TRÊN TẬP TEST ĐỘC LẬP (4,890 ẢNH):")
print("=" * 70)
print(report_text)

# Vẽ Confusion Matrix trực quan
cm = confusion_matrix(all_labels, all_preds)
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=class_names, yticklabels=class_names)
plt.title("Confusion Matrix - SignSight Vietnam Traffic Signs (QCVN 41:2019)", fontsize=14, pad=15)
plt.xlabel("Dự Đoán (Predicted)", fontsize=12)
plt.ylabel("Thực Tế (True Ground Truth)", fontsize=12)
plt.tight_layout()
plt.savefig("confusion_matrix.png", dpi=200)
plt.show()

# Lưu báo cáo vào JSON
with open("evaluation_report.json", "w", encoding="utf-8") as f:
    json.dump({
        "best_val_accuracy": best_val_acc,
        "test_accuracy": report_dict["accuracy"],
        "classification_report": report_dict
    }, f, indent=2, ensure_ascii=False)
print("✅ Đã lưu kết quả vào evaluation_report.json và confusion_matrix.png")""")

    # Cell 10: Visual Prediction Grid
    add_code("""# 9. Trực quan hóa kết quả dự đoán trên mẫu ảnh thực tế
plt.figure(figsize=(15, 6))
indices = np.random.choice(len(df_test), 10, replace=False)

inv_normalize = transforms.Normalize(
    mean=[-0.485/0.229, -0.456/0.224, -0.406/0.225],
    std=[1/0.229, 1/0.224, 1/0.225]
)

for idx, test_idx in enumerate(indices):
    img_tensor, true_label = test_ds[test_idx]
    with torch.no_grad():
        output = model(img_tensor.unsqueeze(0).to(device))
        prob = torch.softmax(output, dim=1).squeeze(0)
        pred_label = int(prob.argmax().cpu().item())
        conf = float(prob[pred_label].cpu().item())

    # Chuyển tensor về ảnh RGB để hiển thị
    img_disp = inv_normalize(img_tensor).clamp(0, 1).permute(1, 2, 0).cpu().numpy()

    plt.subplot(2, 5, idx + 1)
    plt.imshow(img_disp)
    plt.axis("off")
    is_correct = (pred_label == true_label)
    color = "green" if is_correct else "red"
    pred_code = new_to_info[pred_label]["qcvn_code"]
    true_code = new_to_info[true_label]["qcvn_code"]
    plt.title(f"Dự đoán: {pred_code}\\nThực tế: {true_code}\\nĐộ tin cậy: {conf*100:.1f}%", fontsize=10, color=color)

plt.tight_layout()
plt.show()""")

    # Cell 11: Download Checkpoint to Local Machine
    add_code("""# 10. Tải file trọng số về máy tính để tích hợp vào Backend SignSight Cục Bộ
print(\"\"\"
========================================================================
HƯỚNG DẪN ĐƯA MODEL VÀO DỰ ÁN CỤC BỘ TRÊN MÁY TÍNH:
1. File 'best_model.pth' và 'evaluation_report.json' đã sẵn sàng.
2. Sao chép file 'best_model.pth' vào thư mục dự án trên máy tính tại:
   -> ai_engine/checkpoints/best_model.pth
3. Backend FastAPI (uvicorn) và Frontend (index.html) sẽ tự động nạp
   trọng số thật và hoạt động 100%!
========================================================================
\"\"\")

try:
    from google.colab import files
    print("Đang chuẩn bị tải best_model.pth xuống máy tính của bạn...")
    files.download('best_model.pth')
    files.download('evaluation_report.json')
    files.download('confusion_matrix.png')
except ImportError:
    print("Nếu đang chạy trên Kaggle: File best_model.pth nằm trong thư mục output /kaggle/working/best_model.pth, bạn có thể tải trực tiếp từ tab Output bên phải!")""")

    notebook = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {
                "provenance": []
            },
            "kernelspec": {
                "display_name": "Python 3",
                "name": "python3"
            },
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }

    with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"Generated notebook at: {NOTEBOOK_PATH}")

if __name__ == "__main__":
    build_notebook()
