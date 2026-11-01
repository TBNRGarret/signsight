"""Build only the supported standalone EDA and training notebooks."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDA_TARGET = ROOT / 'notebooks/SignSight_SupSign_EDA_Colab.ipynb'
TRAIN_TARGET = ROOT / 'notebooks/SignSight_SupSign_YOLO11s_Train_Colab.ipynb'

def _build(stage):
    notebook = json.loads(Path(__file__).with_name('cells.json').read_text(encoding='utf-8'))[stage]
    embedded = {name: (ROOT/name).read_text(encoding='utf-8') for name in
                ('scripts/dataset_eda.py', 'scripts/supsign_training.py', 'scripts/colab_downloads.py')}
    embedded.update({p.relative_to(ROOT).as_posix():p.read_text(encoding='utf-8') for p in sorted((ROOT/'training').rglob('*.py')) if 'notebooks' not in p.parts and 'legacy_baseline' not in p.parts})
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
