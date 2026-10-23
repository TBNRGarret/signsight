"""Public exports must not inherit academic files, credentials or Git history."""
from pathlib import Path

import pytest

from scripts.prepare_public_repo import export_repository, is_public_path


@pytest.mark.parametrize("name", [
    "COS40006_000000000_Student_Worklog.pdf", "docs/thinh_tasks.md",
    "docs/qa/screenshot.png", "docs/roadmap_12_weeks.md",
    ".git/config", ".cache/login.txt", ".env", "backend/uploads/private.jpg",
    "backend/signsight.db-wal", "ai_engine/checkpoints/detection/best.pt",
    "backend/credentials.json", "../README.md",
])
def test_public_policy_excludes_private_and_runtime_paths(name):
    assert not is_public_path(name)


@pytest.mark.parametrize("name", [
    "README.md", ".env.example", ".github/workflows/ci.yml",
    "backend/app/main.py", "frontend/vendor/maplibre/maplibre-gl-worker.mjs",
    "data/processed/train.csv", "docs/images_and_detection.md",
    "notebooks/SignSight_YOLO_Colab.ipynb",
])
def test_public_policy_keeps_runtime_sources_and_setup(name):
    assert is_public_path(name)


def test_export_sanitizes_drive_references_and_internal_links_without_touching_source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    files = {
        "scripts/generate_drive_eda_notebook.py": "FILE_ID = 'private-drive-fixture'\n",
        "README.md": "# Demo\n[QA](docs/qa/screen.png)\n[Setup](docs/images_and_detection.md)\n",
        "docs/images_and_detection.md": "Use private-drive-fixture\n",
        "docs/qa/screen.png": "private screenshot",
        ".git/config": "private old history",
        "backend/uploads/private.jpg": "private image",
    }
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    result = export_repository(root, root / ".cache/public", list(files))
    assert set(result) == {"README.md", "docs/images_and_detection.md", "scripts/generate_drive_eda_notebook.py"}
    assert not (root / ".cache/public/.git").exists()
    assert not (root / ".cache/public/docs/qa").exists()
    assert "private-drive-fixture" not in (root / ".cache/public/docs/images_and_detection.md").read_text()
    assert "YOUR_DRIVE_FILE_ID" in (root / ".cache/public/scripts/generate_drive_eda_notebook.py").read_text()
    readme = (root / ".cache/public/README.md").read_text(encoding="utf-8")
    assert "docs/qa/screen.png" not in readme
    assert "[Setup](docs/images_and_detection.md)" in readme
    assert (root / "scripts/generate_drive_eda_notebook.py").read_text() == files["scripts/generate_drive_eda_notebook.py"]


def test_export_refuses_existing_or_outside_destination(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    destination = root / "existing"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        export_repository(root, destination, [])
    with pytest.raises(ValueError, match="inside"):
        export_repository(root, tmp_path / "outside", [])
    assert marker.read_text() == "keep"


def test_export_refuses_source_symlink_without_reading_its_target(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    secret = tmp_path / "outside.txt"
    secret.write_text("do not export")
    link = root / "README.md"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("Symlink creation requires local OS privileges")
    with pytest.raises(ValueError, match="symlink"):
        export_repository(root, root / "public", ["README.md"])
    assert not (root / "public").exists()


def test_export_blocks_future_academic_files_in_public_gitignore(tmp_path):
    (tmp_path / ".gitignore").write_text(".cache/\n", encoding="utf-8")
    export_repository(tmp_path, tmp_path / "public", [".gitignore"])
    rules = (tmp_path / "public/.gitignore").read_text(encoding="utf-8")
    assert "/*.docx" in rules and "/*.pdf" in rules and "/docs/qa/" in rules


def test_export_rejects_likely_credential_before_creating_destination(tmp_path):
    source = tmp_path / "backend/app/main.py"
    source.parent.mkdir(parents=True)
    source.write_text("token = " + repr("gh" + "p_" + "x" * 40), encoding="utf-8")
    with pytest.raises(ValueError, match="credential"):
        export_repository(tmp_path, tmp_path / "public", ["backend/app/main.py"])
    assert not (tmp_path / "public").exists()
