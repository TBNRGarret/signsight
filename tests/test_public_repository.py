"""Public exports must not inherit academic files, credentials or Git history."""
from pathlib import Path

import pytest

from scripts.check_public_source import is_public_path


@pytest.mark.parametrize("name", [
    "COS40006_000000000_Student_Worklog.pdf", "docs/thinh_tasks.md",
    "docs/qa/screenshot.png", "docs/roadmap_12_weeks.md",
    ".git/config", ".cache/login.txt", ".env", "backend/uploads/private.jpg",
    "backend/signsight.db-wal", "ai_engine/checkpoints/detection/best.pt",
    "backend/credentials.json", "../README.md",
    "data/supsign/images/photo.jpg", "data/raw/source.csv",
    "ai_engine/checkpoints/model.bin", "docs/student_worklog.md",
])
def test_public_policy_excludes_private_and_runtime_paths(name):
    assert not is_public_path(name)


@pytest.mark.parametrize("name", [
    "README.md", ".env.example", ".github/workflows/ci.yml",
    "backend/app/main.py", "frontend/vendor/maplibre/maplibre-gl-worker.mjs",
    "data/processed/train.csv", "docs/images_and_detection.md",
    "notebooks/SignSight_SupSign_EDA_Colab.ipynb",
    "deploy/Caddyfile.example",
])
def test_public_policy_keeps_runtime_sources_and_setup(name):
    assert is_public_path(name)
