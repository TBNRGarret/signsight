"""
SignSight Project B - Dataset Preparation Script
Filters 10 Vietnam-compatible traffic sign classes from GTSRB dataset (archive/)
Performs Track-Aware Stratified Train/Val Split to guarantee ZERO data leakage.
"""

import os
import json
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "archive")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
TAXONOMY_PATH = os.path.join(DATA_DIR, "taxonomy.json")

def main():
    print("=" * 60)
    print("SignSight: Preparing 10-Class Vietnam Traffic Sign Dataset")
    print("=" * 60)

    # 1. Load Taxonomy
    if not os.path.exists(TAXONOMY_PATH):
        raise FileNotFoundError(f"Taxonomy file not found at {TAXONOMY_PATH}")

    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        taxonomy = json.load(f)

    gtsrb_to_new = {item["gtsrb_id"]: item["new_id"] for item in taxonomy}
    new_to_info = {item["new_id"]: item for item in taxonomy}
    target_classes = list(gtsrb_to_new.keys())
    print(f"Loaded {len(taxonomy)} target classes: {target_classes}")

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # 2. Process Training Set with Track-Aware Split
    train_csv_path = os.path.join(ARCHIVE_DIR, "Train.csv")
    if not os.path.exists(train_csv_path):
        raise FileNotFoundError(f"Missing {train_csv_path}")

    raw_train = pd.read_csv(train_csv_path)
    df_train_filtered = raw_train[raw_train["ClassId"].isin(target_classes)].copy()

    # Map to new 0-9 class IDs
    df_train_filtered["NewClassId"] = df_train_filtered["ClassId"].map(gtsrb_to_new)
    df_train_filtered["QCVN_Code"] = df_train_filtered["NewClassId"].apply(lambda cid: new_to_info[cid]["qcvn_code"])
    df_train_filtered["Name_VI"] = df_train_filtered["NewClassId"].apply(lambda cid: new_to_info[cid]["name_vi"])

    # Extract TrackId from path: e.g. Train/02/00002_00015_00029.png -> track "00015"
    def extract_track(path_str):
        filename = os.path.basename(path_str)
        parts = filename.split("_")
        if len(parts) >= 2:
            return parts[1]
        return filename

    df_train_filtered["TrackId"] = df_train_filtered["Path"].apply(extract_track)
    # Unique compound track identifier across classes
    df_train_filtered["CompoundTrackId"] = df_train_filtered["NewClassId"].astype(str) + "_" + df_train_filtered["TrackId"]

    # Stratified Split by Track (80% Train, 20% Val)
    np.random.seed(42)  # For reproducibility
    train_tracks = []
    val_tracks = []

    for new_cid in sorted(df_train_filtered["NewClassId"].unique()):
        class_tracks = df_train_filtered[df_train_filtered["NewClassId"] == new_cid]["CompoundTrackId"].unique()
        n_tracks = len(class_tracks)
        shuffled = np.random.permutation(class_tracks)
        n_val = max(1, int(round(n_tracks * 0.20)))

        val_sel = shuffled[:n_val]
        train_sel = shuffled[n_val:]

        val_tracks.extend(val_sel)
        train_tracks.extend(train_sel)

    train_tracks_set = set(train_tracks)
    val_tracks_set = set(val_tracks)

    # Verification: Zero track overlap
    leakage = train_tracks_set.intersection(val_tracks_set)
    assert len(leakage) == 0, f"DATA LEAKAGE DETECTED! Overlapping tracks: {leakage}"

    df_train_final = df_train_filtered[df_train_filtered["CompoundTrackId"].isin(train_tracks_set)].copy()
    df_val_final = df_train_filtered[df_train_filtered["CompoundTrackId"].isin(val_tracks_set)].copy()

    # 3. Process Test Set
    test_csv_path = os.path.join(ARCHIVE_DIR, "Test.csv")
    if not os.path.exists(test_csv_path):
        raise FileNotFoundError(f"Missing {test_csv_path}")

    raw_test = pd.read_csv(test_csv_path)
    df_test_filtered = raw_test[raw_test["ClassId"].isin(target_classes)].copy()
    df_test_filtered["NewClassId"] = df_test_filtered["ClassId"].map(gtsrb_to_new)
    df_test_filtered["QCVN_Code"] = df_test_filtered["NewClassId"].apply(lambda cid: new_to_info[cid]["qcvn_code"])
    df_test_filtered["Name_VI"] = df_test_filtered["NewClassId"].apply(lambda cid: new_to_info[cid]["name_vi"])

    # 4. Save Processed CSVs
    train_out = os.path.join(PROCESSED_DIR, "train.csv")
    val_out = os.path.join(PROCESSED_DIR, "val.csv")
    test_out = os.path.join(PROCESSED_DIR, "test.csv")

    df_train_final.to_csv(train_out, index=False)
    df_val_final.to_csv(val_out, index=False)
    df_test_filtered.to_csv(test_out, index=False)

    # 5. Summary Statistics
    print("\n" + "=" * 70)
    print(f"{'NewID':<6} | {'QCVN Code':<12} | {'Train':<8} | {'Val':<8} | {'Test':<8} | {'Total':<8}")
    print("-" * 70)

    total_tr, total_va, total_te = 0, 0, 0
    for cid in range(10):
        info = new_to_info[cid]
        tr_cnt = (df_train_final["NewClassId"] == cid).sum()
        va_cnt = (df_val_final["NewClassId"] == cid).sum()
        te_cnt = (df_test_filtered["NewClassId"] == cid).sum()
        tot = tr_cnt + va_cnt + te_cnt
        total_tr += tr_cnt
        total_va += va_cnt
        total_te += te_cnt
        print(f"{cid:<6} | {info['qcvn_code']:<12} | {tr_cnt:<8} | {va_cnt:<8} | {te_cnt:<8} | {tot:<8}")

    print("-" * 70)
    print(f"{'TOTAL':<6} | {'ALL 10':<12} | {total_tr:<8} | {total_va:<8} | {total_te:<8} | {total_tr + total_va + total_te:<8}")
    print("=" * 70)
    print(f"[OK] Training Split:   {train_out} ({len(df_train_final)} rows, {len(train_tracks_set)} tracks)")
    print(f"[OK] Validation Split: {val_out} ({len(df_val_final)} rows, {len(val_tracks_set)} tracks)")
    print(f"[OK] Test Split:       {test_out} ({len(df_test_filtered)} rows)")
    print("[OK] Track-level leakage verification: PASSED (0 overlapping tracks)")

if __name__ == "__main__":
    main()
