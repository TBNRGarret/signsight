import json
from pathlib import Path
import subprocess
import sys


def test_standalone_notebook_mounts_drive_and_audits_zip_with_full_defaults(tmp_path):
    from training.notebooks.vitsd import build_notebook
    notebook = build_notebook()
    cells = {c['id']: ''.join(c['source']) for c in notebook['cells']}
    assert "drive.mount('/content/drive')" in cells['mount']
    assert 'gdown' not in cells['install']
    assert 'MAX_IMAGES = None' in cells['config']
    assert 'COPY_ZIP_TO_LOCAL = True' in cells['config']
    assert 'REFERENCE_MANIFEST_PATH' in cells['config']
    assert 'files.download' in cells['export']
    for c in notebook['cells']:
        if c['cell_type'] == 'code':
            compile(''.join(c['source']), f"cell:{c['id']}", 'exec')
            assert c['outputs'] == [] and c['execution_count'] is None
    # Actually execute the embedded helper in an isolated fresh Python process,
    # without the repository on sys.path and without accessing Drive/network.
    pipeline = cells['pipeline']
    script = f"""from pathlib import Path
import sys
WORK = Path({str(tmp_path)!r})
{pipeline}
assert callable(audit_zip) and callable(write_review)
assert str(WORK) in __import__('training.data.vitsd_review', fromlist=['x']).__file__
"""
    runner = tmp_path / 'standalone.py'
    runner.write_text(script, encoding='utf-8')
    process = subprocess.run([sys.executable, '-I', str(runner)], cwd=tmp_path,
                             capture_output=True, encoding='utf-8')
    assert process.returncode == 0, process.stderr


def test_generated_notebook_matches_the_committed_artifact():
    from training.notebooks.vitsd import build_notebook, TARGET
    assert json.loads(TARGET.read_text(encoding='utf-8')) == build_notebook()


def test_notebook_cells_copy_audit_export_and_reuse_cache_in_fresh_runtime(tmp_path):
    from training.notebooks.vitsd import build_notebook
    cells = {c['id']: ''.join(c['source']) for c in build_notebook()['cells']}
    script = '''from pathlib import Path
import sys, io, zipfile, json, types, hashlib, shutil
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
from PIL import Image
WORK = Path.cwd()/'runtime'; WORK.mkdir()
fixture_source = Path.cwd()/'mounted'/'ViTSD.zip'; fixture_source.parent.mkdir()
buffer=io.BytesIO(); Image.new('RGB',(64,32),'blue').save(buffer,format='PNG')
with zipfile.ZipFile(fixture_source,'w') as z:
    z.writestr('data.yaml','names: [Speed_limit_60]')
    for split in ('train','test'):
        z.writestr(f'images/{split}/a.png',buffer.getvalue())
        z.writestr(f'labels/{split}/a.txt','0 .5 .5 .2 .2')
before=hashlib.sha256(fixture_source.read_bytes()).hexdigest()
'''
    script += cells['pipeline']
    script += '''
from datetime import datetime, timezone
DRIVE_ZIP_PATH=str(fixture_source)
REFERENCE_MANIFEST_PATH=''
COPY_ZIP_TO_LOCAL=True
ANNOTATION_FORMAT='yolo'
MAX_IMAGES=None
NEAR_HASH_DISTANCE=4
SAVE_REPORT_TO_DRIVE=True
DRIVE_REPORT_DIR=Path.cwd()/'mounted'/'reports'
DOWNLOAD_REPORT=False
'''
    for name in ('source', 'audit', 'audit', 'review'):
        script += '\n' + cells[name]
    script += '''
colab=types.ModuleType('google.colab'); colab.files=types.SimpleNamespace()
sys.modules['google.colab']=colab
'''
    script += cells['export']
    script += '''
assert hashlib.sha256(fixture_source.read_bytes()).hexdigest()==before
assert len(list(DRIVE_REPORT_DIR.glob('*.zip')))==1
assert report_summary['source']['images_scanned']==2
assert report_summary['training_ready'] is False
assert report_summary['near_duplicates']['cross_split_edges']==1
with zipfile.ZipFile(RESULT_ZIP) as z:
    assert 'index.html' in z.namelist() and 'quarantine.csv' in z.namelist()
'''
    runner = tmp_path/'run_cells.py'; runner.write_text(script, encoding='utf-8')
    process = subprocess.run([sys.executable, '-I', str(runner)], cwd=tmp_path,
                             capture_output=True, encoding='utf-8')
    assert process.returncode == 0, process.stderr
