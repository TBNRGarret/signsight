import base64
import gzip
import hashlib
import stat
import zipfile

import pytest
from test_detection_pipeline import sources


def test_archive_lookup_reuses_local_or_kaggle_input_without_download(tmp_path):
    from ai_engine.notebook_data import resolve_archive
    archive=tmp_path/'input'/'archive'; archive.mkdir(parents=True)
    for name in ('Train.csv','Test.csv'): (archive/name).write_text('annotations')
    def download(_): raise AssertionError('Existing source must not download again')
    assert resolve_archive([tmp_path/'input'],'owner/data/versions/1',download)==archive.resolve()


def test_archive_lookup_downloads_only_when_no_source_exists(tmp_path):
    from ai_engine.notebook_data import resolve_archive
    raw=tmp_path/'downloaded'; raw.mkdir()
    for name in ('Train.csv','Test.csv'): (raw/name).write_text('annotations')
    calls=[]
    def download(handle): calls.append(handle); return raw
    assert resolve_archive([tmp_path/'absent'],'owner/data/versions/1',download)==raw
    assert calls==['owner/data/versions/1']


def test_embedded_splits_roundtrip_and_reject_modified_payload(tmp_path):
    from ai_engine.notebook_data import restore_splits
    contents={name:b'Path,NewClassId\nimage.png,0\n' for name in ('train.csv','val.csv','test.csv')}
    payload={name:base64.b64encode(gzip.compress(data,mtime=0)).decode() for name,data in contents.items()}
    checksums={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
    root=restore_splits(payload,checksums,tmp_path/'csv')
    assert {p.name:p.read_bytes() for p in root.iterdir()}==contents
    payload['train.csv']=base64.b64encode(gzip.compress(b'changed')).decode()
    with pytest.raises(ValueError,match='checksum'): restore_splits(payload,checksums,tmp_path/'bad')


def test_prepared_cache_reuses_valid_data_and_restores_persistent_archive(sources,tmp_path,monkeypatch):
    import ai_engine.notebook_data as module
    archive,csv_root,_=sources
    saved=tmp_path/'drive'
    first,report=module.prepare_cached_dataset(archive,csv_root,tmp_path/'runtime1',source_id='source/v1',persistent_root=saved)
    original=first.read_bytes()
    def no_rebuild(*args,**kwargs): raise AssertionError('Valid cache must not rebuild ROI data')
    monkeypatch.setattr(module,'build_dataset',no_rebuild)
    again,second=module.prepare_cached_dataset(None,csv_root,tmp_path/'runtime1',source_id='source/v1',persistent_root=saved)
    restored,third=module.prepare_cached_dataset(None,csv_root,tmp_path/'runtime2',source_id='source/v1',persistent_root=saved)
    assert first==again and original==restored.read_bytes()
    assert report['sha256']==second['sha256']==third['sha256']
    assert len(list(saved.glob('*.zip')))==1


def test_persistent_cache_tampering_is_rejected_without_rebuild_or_overwrite(sources,tmp_path):
    from ai_engine.notebook_data import prepare_cached_dataset
    archive,csv_root,_=sources; saved=tmp_path/'drive'
    prepare_cached_dataset(archive,csv_root,tmp_path/'runtime',source_id='source/v1',persistent_root=saved)
    cached=next(saved.glob('*.zip')); cached.write_bytes(b'broken')
    with pytest.raises(ValueError,match='checksum'):
        prepare_cached_dataset(None,csv_root,tmp_path/'new-runtime',source_id='source/v1',persistent_root=saved)
    assert cached.read_bytes()==b'broken'


def test_changed_splits_cannot_reuse_old_cache(sources,tmp_path):
    from ai_engine.notebook_data import prepare_cached_dataset
    archive,csv_root,_=sources
    prepare_cached_dataset(archive,csv_root,tmp_path/'cache',source_id='source/v1')
    path=csv_root/'train.csv'; path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='raw source'):
        prepare_cached_dataset(None,csv_root,tmp_path/'cache',source_id='source/v1')


@pytest.mark.parametrize('name', ['../outside', '..\\outside', '/absolute', 'C:\\outside'])
def test_persistent_zip_rejects_unsafe_paths(tmp_path, name):
    from ai_engine.notebook_data import _safe_extract
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr(name, 'bad')
    target = tmp_path / 'output'; target.mkdir()
    with zipfile.ZipFile(archive) as bundle, pytest.raises(ValueError, match='Unsafe'):
        _safe_extract(bundle, target)
    assert not list(target.iterdir())


def test_persistent_zip_rejects_symlinks(tmp_path):
    from ai_engine.notebook_data import _safe_extract
    archive = tmp_path / 'bad.zip'
    info = zipfile.ZipInfo('link')
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr(info, '../outside')
    target = tmp_path / 'output'; target.mkdir()
    with zipfile.ZipFile(archive) as bundle, pytest.raises(ValueError, match='Unsafe'):
        _safe_extract(bundle, target)


def test_changed_cached_labels_are_rejected_and_preserved(sources, tmp_path):
    from ai_engine.notebook_data import prepare_cached_dataset
    archive, csv_root, _ = sources
    data, _ = prepare_cached_dataset(archive, csv_root, tmp_path/'cache', source_id='source/v1')
    label = next((data.parent/'labels/train').glob('*.txt'))
    changed = label.read_text() + '\n'
    label.write_text(changed)
    with pytest.raises(ValueError, match='checksum'):
        prepare_cached_dataset(None, csv_root, tmp_path/'cache', source_id='source/v1')
    assert label.read_text() == changed
