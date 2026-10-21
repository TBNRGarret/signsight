"""Package an already validated YOLO dataset with paths portable to Colab."""
import argparse
from pathlib import Path
import zipfile

import yaml
from ai_engine.prepare_detection_data import NAMES


def package_dataset(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    config = yaml.safe_load((source/'data.yaml').read_text(encoding='utf-8'))
    if config['names'] != dict(enumerate(NAMES)):
        raise ValueError('Dataset taxonomy mismatch')
    for split in ('train','val','test'):
        if config[split] != f'images/{split}' or not (source/'labels'/split).is_dir():
            raise ValueError('Expected validated images/labels split layout')
    config['path'] = '.'
    target.parent.mkdir(parents=True,exist_ok=True)
    bundle = zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1)
    try:
        with bundle:
            bundle.writestr('data.yaml',yaml.safe_dump(config,allow_unicode=True,sort_keys=False))
            manifest = source/'manifest.json'
            if manifest.is_file(): bundle.write(manifest,'manifest.json')
            for directory in ('images','labels'):
                for path in sorted((source/directory).rglob('*')):
                    if path.is_file() and path.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.txt'):
                        if not path.resolve().is_relative_to(source): raise ValueError('Unsafe dataset symlink')
                        bundle.write(path,path.relative_to(source).as_posix())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(package_dataset(args.source,args.output))


if __name__=='__main__': main()
