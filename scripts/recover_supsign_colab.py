"""Paste/run inside the original failed SignSight Colab notebook, before restarting.

Downloads the fixed preparation helper from this repository. Optional
SIGNSIGHT_RECOVERY_REVISION pins both the cell and helper to a reviewed commit.
"""
import importlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen

from tqdm.auto import tqdm

_saved_tb = globals().get('_SIGNSIGHT_PREP_TRACEBACK') or getattr(sys, 'last_traceback', None)
if _saved_tb is None:
    _saved_tb = getattr(getattr(sys, 'last_exc', None), '__traceback__', None)
if _saved_tb is None:
    raise RuntimeError('Original traceback is gone. Use the updated notebook and rerun preparation.')
_SIGNSIGHT_PREP_TRACEBACK = _saved_tb  # Retain the original snapshot if saving cache needs retry.

_helper = sys.modules.get('scripts.supsign_training')
_path = (Path(CODE_ROOT) / 'scripts/supsign_training.py').resolve()
if _helper is None or Path(_helper.__file__).resolve() != _path:
    raise RuntimeError('Run this cell in the original SignSight notebook after its pipeline cell.')
_revision = globals().get('SIGNSIGHT_RECOVERY_REVISION', 'main')
_url = f'https://raw.githubusercontent.com/TBNRGarret/signsight/{_revision}/scripts/supsign_training.py'
with urlopen(_url, timeout=30) as _response:
    _payload = _response.read()
compile(_payload, str(_path), 'exec')  # Reject incomplete downloads before replacing the helper.
_path.write_bytes(_payload)
importlib.invalidate_caches()
_helper = importlib.reload(_helper)
for _name in ('prepare_supsign', 'verify_dataset', 'pack_dataset', 'restore_dataset',
              'train_experiment', 'evaluate_checkpoint', 'summarize_prepared_dataset', 'recipe'):
    globals()[_name] = getattr(_helper, _name)

if DATASET_ROOT.exists():
    verify_dataset(DATASET_ROOT)
    manifest = json.loads((DATASET_ROOT / 'manifest.json').read_text())
    if manifest['recipe']['implementation_sha256'] != _helper.digest_file(_path):
        raise RuntimeError('Existing dataset uses different code. Do not overwrite its cache.')
else:
    print('Recovering audited/grouped rows; source audit and dHash will not run again.', flush=True)
    manifest = _helper.recover_failed_preparation(
        _saved_tb, progress=lambda items, desc, unit: tqdm(items, desc=desc, unit=unit))
RECIPE = manifest['recipe']
if not CACHE_ZIP.exists():
    print('Verifying and saving prepared cache to Drive...', flush=True)
    pack_dataset(DATASET_ROOT, CACHE_ZIP)
else:
    print('Existing Drive cache kept; it was not overwritten. Local dataset is ready.')
print('Train missing:', manifest['missing_classes']['train'])
print('Val/test missing:', {s: manifest['missing_classes'][s] for s in ('val', 'test')})
print('Recovery complete. Continue at EDA; do not rerun the old embedded pipeline cell.')
