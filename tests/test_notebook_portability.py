"""Embedded dataset archives must not depend on the build machine OS."""
import ast
import base64

from scripts.generate_yolo_notebook import build_notebook


def test_notebook_split_archives_use_platform_independent_gzip_headers():
    notebook = build_notebook()
    source = next(
        "".join(cell["source"]) for cell in notebook["cells"]
        if cell["cell_type"] == "code" and "SPLIT_PAYLOAD =" in "".join(cell["source"])
    )
    payload = next(
        ast.literal_eval(node.value) for node in ast.parse(source).body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "SPLIT_PAYLOAD"
    )
    assert set(payload) == {"train.csv", "val.csv", "test.csv"}
    for encoded in payload.values():
        header = base64.b64decode(encoded)[:10]
        assert header[:3] == b"\x1f\x8b\x08"
        assert header[3] == 0  # No machine-specific filename or optional metadata.
        assert header[4:8] == b"\x00" * 4  # No build timestamp.
        assert header[9] == 255, "Gzip OS byte must be portable, not Windows/Linux-specific"
