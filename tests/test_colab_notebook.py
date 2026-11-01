import ast
import json
from pathlib import Path
import zipfile

import pytest
import yaml
from test_detection_pipeline import sources

ROOT = Path(__file__).resolve().parents[1]










def test_packaged_dataset_has_portable_yaml_and_cannot_overwrite(sources, tmp_path):
    from ai_engine.prepare_detection_data import build_dataset
    from scripts.package_yolo_dataset import package_dataset
    archive,csv_root,output = sources
    build_dataset(archive,csv_root,output)
    target = tmp_path/'dataset.zip'
    package_dataset(output,target)
    with zipfile.ZipFile(target) as bundle:
        config = yaml.safe_load(bundle.read('data.yaml'))
        assert config['path'] == '.' and config['test'] == 'images/test'
        assert 'manifest.json' in bundle.namelist()
        assert len([name for name in bundle.namelist() if name.startswith('labels/')]) == 30
    with pytest.raises(FileExistsError):
        package_dataset(output,target)
