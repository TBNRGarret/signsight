import ast
import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from scripts.dataset_eda import DatasetReader, audit_dataset, duplicate_groups


def image(path, color='red', size=(100, 50)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', size, color).save(path)


def test_yolo_pairs_nested_paths_checks_bounds_and_preserves_empty_vs_missing(tmp_path):
    for name in ['valid', 'empty', 'missing', 'invalid']:
        image(tmp_path/f'images/train/{name}.png')
    labels=tmp_path/'labels/train';labels.mkdir(parents=True)
    (tmp_path/'data.yaml').write_text('names: [P.102, W.227]\n',encoding='utf-8')
    (labels/'valid.txt').write_text('1 0.5 0.5 0.2 0.2\n')
    (labels/'empty.txt').write_text('')
    (labels/'invalid.txt').write_text('0 0.99 0.5 0.2 0.2\n1 nan 0.5 0.2 0.2\n')
    with DatasetReader(tmp_path) as reader:
        result=audit_dataset(reader,'sample',hash_limit=10)
    rows={Path(row['path']).stem:row for row in result['images']}
    assert rows['empty']['annotation_status']=='empty_annotation'
    assert rows['missing']['annotation_status']=='missing_annotation'
    assert rows['invalid']['annotation_status']=='invalid_annotation'
    assert result['boxes'][0]['class_name']=='W.227'
    assert result['boxes'][0]['short_side_at_640']==pytest.approx(64)
    assert len(result['issues'])>=2
    assert result['summary']['images_scanned']==4


def test_zip_can_be_audited_without_extracting_and_duplicate_leakage_is_reported(tmp_path):
    buffer=io.BytesIO();Image.new('RGB',(40,40),'blue').save(buffer,format='PNG')
    with zipfile.ZipFile(tmp_path/'dataset.zip','w') as z:
        z.writestr('data.yaml','names: [P.102]')
        for split in ['train','val']:
            z.writestr(f'images/{split}/same.png',buffer.getvalue())
            z.writestr(f'labels/{split}/same.txt','0 0.5 0.5 0.4 0.4')
    with DatasetReader(tmp_path) as reader:
        result=audit_dataset(reader,'zip',hash_limit=None)
    assert result['summary']['images_scanned']==2 and len(result['boxes'])==2
    groups=duplicate_groups(result['images'])
    assert len(groups)==1 and groups[0]['cross_split']
    assert not (tmp_path/'images').exists()


def test_voc_and_coco_use_pixel_boxes_and_do_not_conflate_category_ids(tmp_path):
    image(tmp_path/'JPEGImages/voc.jpg')
    (tmp_path/'Annotations').mkdir()
    (tmp_path/'Annotations/voc.xml').write_text('''<annotation><size><width>100</width><height>50</height></size>
      <object><name>P.102</name><bndbox><xmin>10</xmin><ymin>5</ymin><xmax>30</xmax><ymax>15</ymax></bndbox></object></annotation>''')
    image(tmp_path/'images/test/coco.jpg')
    (tmp_path/'annotations.json').write_text(json.dumps({'images':[{'id':7,'file_name':'images/test/coco.jpg','width':100,'height':50}],
      'categories':[{'id':9,'name':'W.227'}], 'annotations':[{'id':1,'image_id':7,'category_id':9,'bbox':[10,5,20,10]}]}))
    with DatasetReader(tmp_path) as reader:
        result=audit_dataset(reader,'mixed',hash_limit=0)
    assert {row['format'] for row in result['boxes']}=={'voc','coco'}
    assert all(row['width_norm']==pytest.approx(.2) for row in result['boxes'])
    assert all(row['height_norm']==pytest.approx(.2) for row in result['boxes'])
    assert all(row['sha256'] is None for row in result['images'])


def test_conflicting_formats_and_broken_files_are_explicit_not_empty_negatives(tmp_path):
    image(tmp_path/'images/a.png')
    (tmp_path/'labels').mkdir()
    (tmp_path/'labels/a.txt').write_text('0 0.5 0.5 .2 .2')
    (tmp_path/'images/a.xml').write_text('<annotation/>')
    (tmp_path/'images/broken.png').write_bytes(b'not an image')
    with DatasetReader(tmp_path) as reader:
        result=audit_dataset(reader,'test',hash_limit=0)
    assert {row['annotation_status'] for row in result['images']}=={'ambiguous_annotation','unreadable_image'}
    assert not result['boxes']


def test_unmapped_classes_and_segmentation_labels_are_not_silently_remapped(tmp_path):
    image(tmp_path/'images/a.png');image(tmp_path/'images/b.png')
    (tmp_path/'labels').mkdir()
    (tmp_path/'labels/a.txt').write_text('17 .5 .5 .2 .2')
    (tmp_path/'labels/b.txt').write_text('1 .1 .1 .2 .1 .2 .2 .1 .2')
    with DatasetReader(tmp_path) as reader:
        result=audit_dataset(reader,'test',hash_limit=0)
    assert result['boxes'][0]['class_id']=='17' and not result['boxes'][0]['class_mapped']
    assert result['summary']['invalid_annotations']==1
    assert any('5 columns' in row['message'] for row in result['issues'])


def test_sampling_is_reproducible_and_report_marks_partial_coverage(tmp_path):
    for i in range(8):image(tmp_path/f'images/{i}.png')
    with DatasetReader(tmp_path) as reader:
        first=audit_dataset(reader,'sample',image_limit=3,hash_limit=2,seed=42)
        second=audit_dataset(reader,'sample',image_limit=3,hash_limit=2,seed=42)
    assert first['summary']['images_total']==8 and first['summary']['images_scanned']==3
    assert first['summary']['partial_scan']
    assert [r['path'] for r in first['images']]==[r['path'] for r in second['images']]
    assert sum(row['sha256'] is not None for row in first['images'])==2


def test_class_maps_are_scoped_and_conflicts_are_not_silently_chosen(tmp_path):
    image(tmp_path/'Images/a.png');(tmp_path/'Labels').mkdir()
    (tmp_path/'Labels/a.txt').write_text('0 .5 .5 .2 .2')
    (tmp_path/'data.yaml').write_text('names: [P.102]')
    image(tmp_path/'export/images/b.png');(tmp_path/'export/labels').mkdir()
    (tmp_path/'export/labels/b.txt').write_text('0 .5 .5 .2 .2')
    (tmp_path/'export/data.yaml').write_text('names: [W.227]')
    with DatasetReader(tmp_path) as reader:
        result=audit_dataset(reader,'test',hash_limit=0)
    assert {box['class_name'] for box in result['boxes']}=={'P.102','W.227'}
    (tmp_path/'classes.txt').write_text('P.125')
    with DatasetReader(tmp_path) as reader:
        result=audit_dataset(reader,'test',hash_limit=0)
    box=next(row for row in result['boxes'] if row['path']=='Images/a.png')
    assert not box['class_mapped'] and any('Conflicting class maps' in issue['message'] for issue in result['issues'])




