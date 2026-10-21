"""
Training and Evaluation Pipeline for 10-Class Vietnam Traffic Sign Recognition
Uses Track-Aware train/val splits in data/processed/
Reports per-class metrics and confusion matrix.
"""

import os
import sys
import json
import pandas as pd
from PIL import Image

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATA_PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "ai_engine", "checkpoints")

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    import torchvision.transforms as transforms
    from sklearn.metrics import classification_report, confusion_matrix
    from ai_engine.model import TrafficSignCNN
    from ai_engine.config import IMAGE_SIZE, BATCH_SIZE, NUM_CLASSES, LEARNING_RATE, NUM_EPOCHS, TAXONOMY
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

class GTSRBDataset(Dataset if HAS_TORCH else object):
    def __init__(self, csv_file, root_dir, transform=None):
        self.df = pd.read_csv(csv_file)
        self.root_dir = root_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = os.path.join(self.root_dir, row["Path"])
        image = Image.open(img_path).convert("RGB")

        # Crop to ROI if available
        if "Roi.X1" in row and not pd.isna(row["Roi.X1"]):
            x1, y1, x2, y2 = int(row["Roi.X1"]), int(row["Roi.Y1"]), int(row["Roi.X2"]), int(row["Roi.Y2"])
            image = image.crop((x1, y1, x2, y2))

        label = int(row["NewClassId"])

        if self.transform:
            image = self.transform(image)

        return image, label

def evaluate_model(model, loader, device, target_names):
    model.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            _, preds = outputs.max(1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.numpy())

    report = classification_report(all_labels, all_preds, target_names=target_names, digits=4, output_dict=True)
    report_text = classification_report(all_labels, all_preds, target_names=target_names, digits=4)
    conf_mat = confusion_matrix(all_labels, all_preds).tolist()
    return report, report_text, conf_mat

def run_training():
    if not HAS_TORCH:
        print("[ERROR] PyTorch hoặc Scikit-Learn chưa được cài đặt trong môi trường hiện tại.")
        print("Chạy lệnh: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 65)
    print(f"BẮT ĐẦU HUẤN LUYỆN MODEL NHẬN DẠNG BIỂN BÁO VIỆT NAM (QCVN 41)")
    print(f"Thiết bị tính toán: {device} " + (f"({torch.cuda.get_device_name(0)})" if torch.cuda.is_available() else "(CPU)"))
    print("=" * 65)

    train_csv = os.path.join(DATA_PROCESSED_DIR, "train.csv")
    val_csv = os.path.join(DATA_PROCESSED_DIR, "val.csv")
    test_csv = os.path.join(DATA_PROCESSED_DIR, "test.csv")
    archive_dir = os.path.join(PROJECT_ROOT, "archive")

    # Data augmentations mô phỏng thực tế đường sá Việt Nam (ánh sáng gắt/chiều tối, góc nghiêng)
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

    train_dataset = GTSRBDataset(train_csv, archive_dir, transform=train_transform)
    val_dataset = GTSRBDataset(val_csv, archive_dir, transform=val_transform)
    test_dataset = GTSRBDataset(test_csv, archive_dir, transform=val_transform)

    # Dùng num_workers=0 để tương thích tối đa trên Windows
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = TrafficSignCNN(num_classes=NUM_CLASSES).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    best_val_acc = 0.0
    best_weights_path = os.path.join(CHECKPOINT_DIR, "best_model.pth")

    class_names = [f"{item['qcvn_code']}" for item in TAXONOMY]

    print(f"Tổng số mẫu: Train={len(train_dataset)}, Val={len(val_dataset)}, Test={len(test_dataset)}")
    print(f"Batch Size={BATCH_SIZE} | Số Epochs={NUM_EPOCHS} | Tốc độ học (LR)={LEARNING_RATE}\n")

    for epoch in range(1, NUM_EPOCHS + 1):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

        scheduler.step()
        epoch_loss = running_loss / total
        epoch_acc = (correct / total) * 100.0

        # Đánh giá trên tập Validation
        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, predicted = outputs.max(1)
                val_total += labels.size(0)
                val_correct += predicted.eq(labels).sum().item()

        val_acc = (val_correct / val_total) * 100.0
        print(f"Epoch [{epoch:02d}/{NUM_EPOCHS:02d}] Loss: {epoch_loss:.4f} | Train Acc: {epoch_acc:6.2f}% | Val Acc: {val_acc:6.2f}%", end="")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_weights_path)
            print(f" -> [LƯU BEST MODEL: {val_acc:.2f}%]")
        else:
            print("")

    print("\n" + "=" * 65)
    print("HOÀN TẤT HUẤN LUYỆN! ĐANG ĐÁNH GIÁ TRÊN TẬP TEST ĐỘC LẬP...")
    print("=" * 65)

    # Tải lại trọng số tốt nhất để đánh giá trên Test set
    model.load_state_dict(torch.load(best_weights_path, map_location=device, weights_only=True))
    report_dict, report_str, conf_mat = evaluate_model(model, test_loader, device, class_names)

    print("\nBÁO CÁO KẾT QUẢ ĐÁNH GIÁ CHI TIẾT THEO TỪNG LỚP (TEST SET):")
    print(report_str)

    # Lưu báo cáo vào file JSON để dùng cho slide thuyết trình và tài liệu Project B
    report_file = os.path.join(CHECKPOINT_DIR, "evaluation_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "best_val_accuracy": best_val_acc,
            "test_classification_report": report_dict,
            "confusion_matrix": conf_mat,
            "classes": class_names
        }, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Đã lưu model tại: {best_weights_path}")
    print(f"[OK] Đã lưu báo cáo đánh giá tại: {report_file}")

if __name__ == "__main__":
    run_training()
