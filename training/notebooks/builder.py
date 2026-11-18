"""Reproduce archived SupSign V3 notebooks; active CAR35 builder is car35.py."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDA_TARGET = ROOT / 'notebooks/legacy/SignSight_SupSign_EDA_Colab.ipynb'
TRAIN_TARGET = ROOT / 'notebooks/legacy/SignSight_SupSign_YOLO11s_Train_Colab.ipynb'

# Archived notebooks retain their original dependency closure. New, independent
# training pipelines must not silently alter cache fingerprints or artifacts.
LEGACY_MODULES = (
    'training/__init__.py', 'training/compatibility.py',
    'training/data/__init__.py', 'training/data/audit.py', 'training/data/cache.py',
    'training/data/common.py', 'training/data/downloads.py', 'training/data/drive_source.py',
    'training/data/grouping_render.py', 'training/data/grouping_review.py', 'training/data/supsign.py',
    'training/experiments/__init__.py', 'training/experiments/evaluate.py',
    'training/experiments/local_pipeline.py', 'training/experiments/train.py',
)

def _build(stage):
    notebook = json.loads(Path(__file__).with_name('cells.json').read_text(encoding='utf-8'))[stage]
    embedded = {name: (ROOT/name).read_text(encoding='utf-8') for name in
                ('scripts/dataset_eda.py', 'scripts/supsign_training.py', 'scripts/colab_downloads.py')}
    embedded.update({name: (ROOT/name).read_text(encoding='utf-8') for name in LEGACY_MODULES})
    for cell in notebook['cells']:
        if cell['id'] == 'pipeline':
            cell['source'] = ''.join(cell['source']).replace('__EMBEDDED_FILES__', repr(embedded)).splitlines(keepends=True)
    return notebook

def build_eda_notebook():
    return _build('eda')

def build_train_notebook():
    return _build('train')

def main():
    for target,builder in ((EDA_TARGET,build_eda_notebook),(TRAIN_TARGET,build_train_notebook)):
        target.write_text(json.dumps(builder(),ensure_ascii=False,indent=1),encoding='utf-8')
        print(target)

if __name__ == '__main__': main()
