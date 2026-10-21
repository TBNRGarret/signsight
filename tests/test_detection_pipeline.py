import csv
import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
import yaml

from ai_engine.prepare_detection_data import build_dataset, NAMES
from ai_engine.train_detection import validate_dataset, metrics_report, activate


@pytest.fixture
def sources(tmp_path):
    archive, annotations = tmp_path / "archive", tmp_path / "csv"
    archive.mkdir(); annotations.mkdir()
    fields = ['Width','Height','Roi.X1','Roi.Y1','Roi.X2','Roi.Y2','Path','NewClassId','QCVN_Code','CompoundTrackId']
    for split_index,split in enumerate(('train','val','test')):
        rows = []
        for class_id in range(10):
            path = archive / f'{split}_{class_id}.png'
            Image.new('RGB',(40,30),(class_id*20,split_index*70,17)).save(path)
            rows.append(dict(zip(fields,[40,30,4,3,36,27,path.name,class_id,NAMES[class_id],f'{split}_{class_id}' if split != 'test' else ''])))
        with (annotations/f'{split}.csv').open('w',newline='',encoding='utf-8') as target:
            writer = csv.DictWriter(target,fields); writer.writeheader(); writer.writerows(rows)
    return archive,annotations,tmp_path/'dataset'


def change_row(csv_root,split,key,value):
    path = csv_root / f'{split}.csv'
    with path.open(newline='',encoding='utf-8') as source:
        reader = csv.DictReader(source); fields = reader.fieldnames; rows = list(reader)
    rows[0][key] = value
    with path.open('w',newline='',encoding='utf-8') as target:
        writer = csv.DictWriter(target,fields); writer.writeheader(); writer.writerows(rows)


def test_conversion_validation_and_manifest(sources):
    archive,csv_root,output = sources
    assert build_dataset(archive,csv_root,output) == {'train':10,'val':10,'test':10}
    result = validate_dataset(output/'data.yaml')
    assert result['domain'] == 'gtsrb_roi_bootstrap' and len(result['sha256']) == 64
    assert result['splits']['train'] == {'images':10,'instances':10}
    label = next((output/'labels/train').glob('*.txt')).read_text().split()
    assert list(map(float,label[1:])) == [.5,.5,.8,.8]
    manifest = json.loads((output/'manifest.json').read_text())
    assert manifest['names'] == NAMES
    with pytest.raises(ValueError,match='already exists'):
        build_dataset(archive,csv_root,output)


@pytest.mark.parametrize('key,value,error',[('CompoundTrackId','train_0','Track leakage'),
    ('Path','../outside.png','unsafe'),('Roi.X2','41','Invalid ROI'),('QCVN_Code','person','taxonomy')])
def test_converter_rejects_leakage_unsafe_paths_bad_roi_and_taxonomy(sources,key,value,error):
    archive,csv_root,output = sources
    change_row(csv_root,'val',key,value)
    with pytest.raises(ValueError,match=error):
        build_dataset(archive,csv_root,output)
    assert not output.exists()


def test_content_leakage_rejected(sources):
    archive,csv_root,output = sources
    (archive/'val_0.png').write_bytes((archive/'train_0.png').read_bytes())
    with pytest.raises(ValueError,match='Identical image'):
        build_dataset(archive,csv_root,output)


def test_explicit_deduplication_preserves_test_and_records_exclusions(sources):
    archive,csv_root,output = sources
    # Add a duplicate test copy to training, retaining a distinct original training example.
    with (csv_root/'train.csv').open(newline='',encoding='utf-8') as source:
        reader = csv.DictReader(source); fields = reader.fieldnames; rows = list(reader)
    duplicate = dict(rows[0]); duplicate['Path']='train_copy.png'; duplicate['CompoundTrackId']='extra_train'
    (archive/'train_copy.png').write_bytes((archive/'test_0.png').read_bytes())
    with (csv_root/'train.csv').open('w',newline='',encoding='utf-8') as target:
        writer = csv.DictWriter(target,fields); writer.writeheader(); writer.writerows(rows+[duplicate])
    build_dataset(archive,csv_root,output,deduplicate_overlaps=True)
    assert validate_dataset(output/'data.yaml')['splits']['train']['images'] == 10
    manifest = json.loads((output/'manifest.json').read_text())
    assert manifest['deduplication']['dropped'][0]['source'] == 'train_copy.png'
    assert len(manifest['splits']['test']) == 10 and (archive/'train_copy.png').is_file()


def test_training_validation_rejects_missing_labels_out_of_bounds_and_wrong_names(sources):
    archive,csv_root,output = sources
    build_dataset(archive,csv_root,output)
    label = next((output/'labels/train').glob('*.txt')); original = label.read_text()
    label.unlink()
    with pytest.raises(ValueError,match='Missing label'):
        validate_dataset(output/'data.yaml')
    label.write_text('0 0.9 0.5 0.8 0.8\n')
    with pytest.raises(ValueError,match='bounds'):
        validate_dataset(output/'data.yaml')
    label.write_text(original)
    config = yaml.safe_load((output/'data.yaml').read_text()); config['names'][0] = 'person'
    (output/'data.yaml').write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError,match='names'):
        validate_dataset(output/'data.yaml')


def test_metrics_do_not_fill_missing_class_values():
    box = SimpleNamespace(mp=.8,mr=.7,map50=.6,map=.5,p=np.array([.8]),r=np.array([.7]),
                          ap50=np.array([.6]),ap=np.array([.5]),ap_class_index=np.array([9]))
    report = metrics_report(SimpleNamespace(box=box))
    assert report['per_class'][NAMES[0]] is None and report['per_class'][NAMES[9]]['map50_95'] == .5


def test_checkpoint_activation_preserves_previous_file(tmp_path):
    source = tmp_path/'trained.pt'; source.write_bytes(b'new weights')
    destination = tmp_path/'active/best.pt'; destination.parent.mkdir(); destination.write_bytes(b'old weights')
    activate(source,destination)
    assert destination.read_bytes() == b'new weights'
    assert next(destination.parent.glob('best.*.pt')).read_bytes() == b'old weights'


def test_train_cli_runs_both_eval_splits_and_records_report(sources,monkeypatch):
    import sys
    from ai_engine import train_detection
    archive,csv_root,output = sources
    build_dataset(archive,csv_root,output)
    run = output.parent/'run'; evaluated = []
    class Model:
        task = 'detect'
        names = dict(enumerate(NAMES))
        def __init__(self,*args,**kwargs):
            pass
        def train(self,**kwargs):
            assert kwargs['fliplr'] == kwargs['flipud'] == 0 and kwargs['workers'] == 0
            weights = run/'weights/best.pt'; weights.parent.mkdir(parents=True); weights.write_bytes(b'fake test weights')
            self.trainer = SimpleNamespace(best=weights)
        def val(self,**kwargs):
            evaluated.append(kwargs['split'])
            return SimpleNamespace(box=SimpleNamespace(mp=.8,mr=.7,map50=.6,map=.5,p=np.ones(10)*.8,
                r=np.ones(10)*.7,ap50=np.ones(10)*.6,ap=np.ones(10)*.5,ap_class_index=np.arange(10)))
    monkeypatch.setitem(sys.modules,'ultralytics',SimpleNamespace(YOLO=Model,__version__='unit-test'))
    monkeypatch.setattr(sys,'argv',['train_detection','train','--data',str(output/'data.yaml'),'--model','yolo11n.yaml',
                                   '--output',str(run),'--epochs','1','--smoke'])
    train_detection.main()
    report = json.loads((run/'detection_report.json').read_text())
    assert evaluated == ['val','test'] and report['smoke'] is True
    assert report['model_version'].startswith('sha256:') and report['metrics']['test']['map50'] == .6


@pytest.mark.parametrize('confidence', [.25, .65])
def test_detector_adapter_enforces_taxonomy_and_returns_pixel_boxes(tmp_path,monkeypatch,confidence):
    import sys
    from ai_engine.detection import YoloDetector, DetectorUnavailable
    weights = tmp_path/'detector.pt'; weights.write_bytes(b'adapter test fixture')
    class Tensor:
        def __init__(self,values): self.values = values
        def cpu(self): return self
        def tolist(self): return self.values
    class Model:
        task = 'detect'
        names = dict(enumerate(NAMES))
        def __init__(self,*args,**kwargs): pass
        def predict(self,**kwargs):
            assert kwargs['conf'] == confidence and kwargs['max_det'] == 25
            return [SimpleNamespace(boxes=SimpleNamespace(xyxy=Tensor([[-1,2,101,40],[40,5,90,75]]),
                                                          conf=Tensor([.9,.6]),cls=Tensor([0.,9.])))]
    monkeypatch.setitem(sys.modules,'ultralytics',SimpleNamespace(YOLO=Model))
    detector = YoloDetector(weights, confidence=confidence)
    result = detector.predict(Image.new('RGB',(100,80)))
    assert len(result.predictions) == 2 and result.predictions[0].bbox == (0.,2,100,40)
    assert result.predictions[1].predicted_class == 9
    assert detector.status()['ready'] is True
    Model.names = {0:'person'}
    wrong = YoloDetector(weights)
    with pytest.raises(DetectorUnavailable,match='taxonomy'):
        wrong.predict(Image.new('RGB',(100,80)))
    assert wrong.status()['reason'] == 'taxonomy_mismatch'


@pytest.mark.parametrize('confidence', [0, -.1, 1.1, float('nan'), float('inf')])
def test_detector_rejects_invalid_confidence(tmp_path, confidence):
    from ai_engine.detection import YoloDetector
    with pytest.raises(ValueError, match='confidence'):
        YoloDetector(tmp_path/'weights.pt', confidence=confidence)


def test_api_confidence_setting_reaches_detector(tmp_path, monkeypatch):
    from backend.app.core.settings import Settings
    from backend.app.db.database import make_engine
    from backend.app.main import create_app
    assert Settings().yolo_confidence == .65
    monkeypatch.setenv('SIGNSIGHT_YOLO_CONFIDENCE', '0.42')
    settings = Settings.from_env()
    assert settings.yolo_confidence == .42
    engine = make_engine(f"sqlite:///{tmp_path/'settings.db'}")
    try:
        app = create_app(engine, settings)
        assert app.state.detector.confidence == .42
    finally:
        engine.dispose()


@pytest.mark.parametrize('confidence', ['0', '-0.1', '1.1', 'nan', 'inf'])
def test_api_rejects_invalid_confidence_setting(monkeypatch, confidence):
    from backend.app.core.settings import Settings
    monkeypatch.setenv('SIGNSIGHT_YOLO_CONFIDENCE', confidence)
    with pytest.raises(ValueError, match='confidence'):
        Settings.from_env()


def test_detector_configuration_prepares_an_explicit_writable_settings_directory(tmp_path, monkeypatch):
    from ai_engine.detection import configure_ultralytics
    config = tmp_path / "fresh-checkout" / "yolo-settings"
    monkeypatch.setenv("YOLO_CONFIG_DIR", str(config))
    monkeypatch.delenv("YOLO_AUTOINSTALL", raising=False)
    configure_ultralytics()
    assert config.is_dir(), "A new checkout must not fall back to writing Ultralytics/ into source"
    import os
    assert os.environ["YOLO_AUTOINSTALL"] == "false"
