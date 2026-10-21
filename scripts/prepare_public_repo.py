"""Export an explicit public source subset, without copying or rewriting Git history.

Read-only on the source; destination must be new and inside the source workspace.
No network calls, deletion, Git initialization or pushing.
"""
import argparse
import ast
import posixpath
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {".gitattributes", ".gitignore", ".env.example", "README.md", "CONTRIBUTING.md", "pytest.ini", "package.json", "package-lock.json", "playwright.config.cjs"}
TECHNICAL_DOCS = {
    "authentication_setup.md", "demo_benchmark.md", "drive_dataset_eda.md",
    "field_capture_quickstart.md", "field_dataset_protocol.md", "images_and_detection.md",
    "iphone_ipad_testing.md", "local_vietnam_pipeline.md", "vietnam_dataset_eda.md",
    "vn_traffic_standards_mapping.md", "web_and_management.md", "github_preparation.md", "local_development.md", "contribution_flow.md",
}
SOURCE_SUFFIXES = {".py", ".txt", ".ini", ".json", ".sql", ".html", ".css", ".js", ".cjs", ".ipynb"}
SENSITIVE_NAMES = {".env", "credentials.json", "kaggle.json", "login.txt"}
SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def is_public_path(name):
    if "\\" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return False
    if any(part in {".git", ".cache", "__pycache__", "node_modules", ".venv", ".venv-yolo"} for part in path.parts):
        return False
    if path.name in SENSITIVE_NAMES:
        return False
    if name in ROOT_FILES:
        return True
    if name in {".github/workflows/ci.yml", ".github/pull_request_template.md"}:
        return True
    if path.parts[0] == "docs":
        return len(path.parts) == 2 and path.name in TECHNICAL_DOCS
    if path.parts[0] == "data":
        return name == "data/taxonomy.json" or (
            path.parent.as_posix() == "data/processed" and path.name in {"train.csv", "val.csv", "test.csv"}
        )
    if name == "tests/browser/fixtures/sign.png":
        return True
    if name.startswith("backend/uploads/"):
        return name == "backend/uploads/.gitkeep"
    if name.startswith("ai_engine/checkpoints/"):
        return name in {"ai_engine/checkpoints/.gitkeep", "ai_engine/checkpoints/detection/detection_report.json"}
    if name.startswith("frontend/vendor/leaflet/"):
        return path.suffix in {".css", ".js", ".png"} or path.name == "LICENSE"
    return path.parts[0] in {"backend", "frontend", "ai_engine", "scripts", "tests", "database", "notebooks"} and path.suffix in SOURCE_SUFFIXES


def _redact_internal_links(text, name, selected):
    def replace(match):
        label, target = match.groups()
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
            return match.group(0)
        target_path = target.split("#", 1)[0]
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target_path))
        if resolved not in selected:
            return label + " (tài liệu nội bộ, không kèm bản public)"
        return match.group(0)
    return re.sub(r"\[([^\]]*)\]\(([^)\n]+)\)", replace, text)


def export_repository(root, destination, paths):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if destination == root or not destination.is_relative_to(root):
        raise ValueError("Destination must be inside the source workspace")
    if destination.exists():
        raise FileExistsError("Destination exists; choose a new path to preserve it")
    selected = sorted({name for name in paths if is_public_path(name)})
    # Reject symlink/junction traversal and missing sources before creating anything.
    for name in selected:
        source = root / name
        if source.is_symlink() or source.resolve() != source.absolute():
            raise ValueError("Refusing symlink or redirected source: " + name)
        if not source.is_file():
            raise FileNotFoundError(name)
    private_id = None
    generator = "scripts/generate_drive_eda_notebook.py"
    if generator in selected:
        tree = ast.parse((root / generator).read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "FILE_ID" for target in node.targets):
                private_id = ast.literal_eval(node.value)
    prepared = {}
    for name in selected:
        content = (root / name).read_bytes()
        # Preserve exact upstream Leaflet bytes: its assets use SRI hashes.
        if name.startswith("frontend/vendor/") or name == "tests/browser/fixtures/sign.png":
            prepared[name] = content
            continue
        if b"\x00" in content:
            raise ValueError("Unexpected binary source: " + name)
        text = content.decode("utf-8")
        if private_id:
            text = text.replace(private_id, "YOUR_DRIVE_FILE_ID")
        if name == ".gitignore":
            text += "\n# Keep academic documents out of the public repository\n/*.docx\n/*.pdf\n/docs/qa/\n/docs/thinh_tasks.md\n/docs/roadmap_12_weeks.md\n/docs/implementation_plan.md\n"
        if name.endswith(".md"):
            text = _redact_internal_links(text, name, set(selected))
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            raise ValueError("Possible credential in source file (value hidden): " + name)
        prepared[name] = text.encode("utf-8")
    destination.mkdir(parents=True, exist_ok=False)
    for name, content in prepared.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
    ).decode("utf-8").split("\0")
    destination = args.output if args.output.is_absolute() else ROOT / args.output
    selected = export_repository(ROOT, destination, paths)
    print(f"Exported {len(selected)} public files to {destination.resolve()}")
    print("No Git history, runtime files or academic reports copied. Source untouched.")
    for name in selected:
        print(name)


if __name__ == "__main__":
    main()
