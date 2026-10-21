import io
import json
import zipfile

from PIL import Image
import pytest

from scripts.dataset_eda import DatasetReader, audit_dataset


def mixed_zip(path):
    image = io.BytesIO(); Image.new('RGB', (100, 100), 'red').save(image, format='PNG')
    coco = {'images': [{'id': 1, 'file_name': 'images/train/a.png', 'width': 100, 'height': 100}],
            'categories': [{'id': 7, 'name': 'W.227'}],
            'annotations': [{'image_id': 1, 'category_id': 7, 'bbox': [10, 10, 20, 20]}]}
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('ViTSD/images/train/a.png', image.getvalue())
        archive.writestr('ViTSD/labels/train/a.txt', '0 .5 .5 .4 .4')
        archive.writestr('ViTSD/data.yaml', 'names: [P.102]')
        archive.writestr('ViTSD/annotations/instances_train.json', json.dumps(coco))


def test_explicit_annotation_format_resolves_mixed_exports_without_merging(tmp_path):
    source = tmp_path / 'archive.zip'; mixed_zip(source)
    with DatasetReader(source) as reader:
        auto = audit_dataset(reader, 'fixture', hash_limit=0)
        assert auto['images'][0]['annotation_status'] == 'ambiguous_annotation'
        yolo = audit_dataset(reader, 'fixture', hash_limit=0, annotation_format='yolo')
        coco = audit_dataset(reader, 'fixture', hash_limit=0, annotation_format='coco')
    assert yolo['summary']['valid_boxes'] == coco['summary']['valid_boxes'] == 1
    assert yolo['boxes'][0]['class_name'] == 'P.102'
    assert yolo['boxes'][0]['width_norm'] == pytest.approx(.4)
    assert coco['boxes'][0]['class_name'] == 'W.227'
    assert coco['boxes'][0]['width_norm'] == pytest.approx(.2)
    assert yolo['summary']['annotation_format'] == 'yolo'
    assert coco['summary']['annotation_format'] == 'coco'


def test_format_choice_never_silently_falls_back_to_a_different_export(tmp_path):
    source = tmp_path / 'archive.zip'; mixed_zip(source)
    with DatasetReader(source) as reader:
        result = audit_dataset(reader, 'fixture', hash_limit=0, annotation_format='voc')
        assert result['summary']['valid_boxes'] == 0
        assert result['images'][0]['annotation_status'] == 'missing_annotation'
        with pytest.raises(ValueError, match='format'):
            audit_dataset(reader, 'fixture', annotation_format='prefer-anything')
