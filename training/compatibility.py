"""Explicit cache provenance checks; content identity is separate from file checksum."""
import hashlib
import json
from pathlib import Path

LEGACY_SIGNATURES = {
 ('42132e8eb337a7d8c27ef35eb5b81688f879d01afaccf593fa88265c435f4eba',
  'f89bb8e458fc951cb997f2de1e57497eeaf61f97a5824e179b66b33bde3e1e03'),
 ('ca8ef48fb483c142085aae0dc6ff9bb570074eac968c686ad4ec2ae4672bbf51',
  '1893e87f0b5fff1719b1590a1bbbb511c1dd40714cf8e3ff4c7bf760eb5b91b1'),
}

def implementation_digest():
    root=Path(__file__).parent
    names=['compatibility.py','data/common.py','data/supsign.py','data/cache.py',
           'experiments/train.py','experiments/evaluate.py']
    content={name:(root/name).read_text(encoding='utf-8') for name in names}
    return hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest()

def require_compatible_recipe(saved, expected=None):
    from training.data.common import recipe
    try:
        current=recipe(saved['classes'],saved['seed'],saved['block_size'],saved['near_threshold'])
        current['groups_sha256']=saved['groups_sha256']
        legacy = saved['version']==1 and (saved['implementation_sha256'],saved['reader_sha256']) in LEGACY_SIGNATURES
        if legacy:
            comparable={k:v for k,v in saved.items() if k not in ('version','implementation_sha256','reader_sha256')}
            if comparable!={k:v for k,v in current.items() if k not in ('version','implementation_sha256','reader_sha256')}:
                raise ValueError('Legacy cache recipe parameters changed')
        elif saved!=current:
            raise ValueError('Unsupported cache recipe/code; use a new dataset version')
        if expected is not None:
            keys=('classes','seed','block_size','near_threshold','groups_sha256')
            if any(saved.get(k)!=expected.get(k) for k in keys):
                raise ValueError('Cache recipe changed; choose a new cache version')
    except (KeyError,TypeError) as error:
        raise ValueError('Invalid cache recipe') from error

def dataset_content_fingerprint(manifest):
    content={k:manifest[k] for k in ('names','source_zip_sha256','recipe')}
    content['images']=sorted(({k:r[k] for k in ('sha256','label_sha256','group','split')}
                              for r in manifest['images']),key=lambda r:r['sha256'])
    return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
