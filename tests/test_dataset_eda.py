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


@pytest.mark.parametrize('mode',['yolo','images_only','no_images'])
def test_notebook_analysis_and_download_cells_execute_on_a_small_offline_dataset(tmp_path,monkeypatch,mode):
    import importlib.metadata
    import shutil
    import sys
    import types
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    import pandas as pd
    from datetime import datetime,timezone
    from scripts.generate_eda_notebook import build_notebook
    import scripts.dataset_eda as eda

    (tmp_path/'input').mkdir()
    if mode!='no_images':
        image(tmp_path/'input/images/train/a.png')
        image(tmp_path/'input/images/val/b.png')
    if mode=='yolo':
        (tmp_path/'input/labels/train').mkdir(parents=True)
        (tmp_path/'input/labels/val').mkdir(parents=True)
        for split,name in [('train','a'),('val','b')]:
            (tmp_path/f'input/labels/{split}/{name}.txt').write_text('0 .5 .5 .2 .2')
        (tmp_path/'input/data.yaml').write_text('names: [P.102]')
    out=tmp_path/'report';out.mkdir()
    downloads=[]
    google=types.ModuleType('google');colab=types.ModuleType('google.colab')
    colab.files=types.SimpleNamespace(download=downloads.append);google.colab=colab
    monkeypatch.setitem(sys.modules,'google',google);monkeypatch.setitem(sys.modules,'google.colab',colab)
    monkeypatch.setattr(importlib.metadata,'version',lambda name:'test-version')
    monkeypatch.setattr(plt,'show',lambda:None)
    context={'Path':Path,'ROOTS':{'fixture':tmp_path/'input'},'eda':eda,'MAX_IMAGES':None,'HASH_LIMIT':None,
             'SEED':42,'VERIFY_DECODE':True,'tqdm':lambda values,**kw:values,'pd':pd,'display':lambda *_:None,
             'plt':plt,'patches':patches,'Image':Image,'OUT':out,'PERSISTENT':None,'ACTIVE_DATASETS':['fixture'],
             'SOURCE_ERRORS':[],'datetime':datetime,'timezone':timezone,'json':json,'shutil':shutil,'importlib':__import__('importlib')}
    cells=[''.join(c['source']) for c in build_notebook()['cells'] if c['cell_type']=='code']
    try:
        for marker in ["for old_reader", "class_columns =", "chosen =", "def export_csv"]:
            exec(next(source for source in cells if source.startswith(marker)),context)
        assert (out/'distributions.png').stat().st_size>1000
        assert (out/'samples.png').exists()==(mode!='no_images')
        assert len(downloads)==1 and Path(downloads[0]).is_file()
        summary=json.loads((out/'summary.json').read_text())
        assert summary['datasets']['fixture']['valid_boxes']==(2 if mode=='yolo' else 0)
        assert summary['exact_duplicate_groups']==(0 if mode=='no_images' else 1)
        assert len(pd.read_csv(out/'class_counts.csv'))==(1 if mode=='yolo' else 0)
    finally:
        for reader in context.get('READERS',{}).values():reader.close()
        plt.close('all')


def test_generated_notebook_is_standalone_parseable_and_contains_no_outputs():
    from scripts.generate_eda_notebook import build_notebook
    notebook=build_notebook()
    packaged=json.loads((Path(__file__).parents[1]/'notebooks/SignSight_Vietnam_Dataset_EDA_Colab.ipynb').read_text(encoding='utf-8'))
    assert notebook==packaged
    for cell in notebook['cells']:
        if cell['cell_type']=='code':ast.parse(''.join(cell['source']))
        assert not cell.get('outputs')
    all_code='\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code')
    assert 'files.download' in all_code and 'kagglehub.dataset_download' in all_code
    assert 'trnghiutrng/supsign/versions/1' in all_code and 'trnghiutrng/vitsdb/versions/1' in all_code
