import copy
import json
import pytest


def test_content_fingerprint_ignores_runtime_path_but_binds_labels_and_split():
    import training.compatibility as compatibility
    value = dict(names=['No_entry'], source_zip_sha256='source',
                 recipe=dict(version=2, classes=['No_entry'], seed=42),
                 images=[dict(sha256='image', label_sha256='label', split='train', group='g')],
                 source_summary=dict(root='/old-runtime/source.zip'))
    relocated = copy.deepcopy(value); relocated['source_summary']['root'] = '/new-runtime/source.zip'
    assert compatibility.dataset_content_fingerprint(value) == compatibility.dataset_content_fingerprint(relocated)
    for key in ('sha256','label_sha256','split','group'):
        changed = copy.deepcopy(value); changed['images'][0][key] = 'different'
        assert compatibility.dataset_content_fingerprint(value) != compatibility.dataset_content_fingerprint(changed)


def test_legacy_cache_is_verified_and_keeps_original_manifest(tmp_path):
    from test_supsign_training import prepare
    from scripts.supsign_training import pack_dataset, restore_dataset
    _, root, _ = prepare(tmp_path)
    path = root/'manifest.json'; manifest=json.loads(path.read_text())
    manifest['recipe'].update(version=1,
        implementation_sha256='42132e8eb337a7d8c27ef35eb5b81688f879d01afaccf593fa88265c435f4eba',
        reader_sha256='f89bb8e458fc951cb997f2de1e57497eeaf61f97a5824e179b66b33bde3e1e03')
    path.write_text(json.dumps(manifest), encoding='utf-8'); original=path.read_bytes()
    cache=tmp_path/'old.zip';pack_dataset(root,cache)
    restored=tmp_path/'restored';restore_dataset(cache,restored)
    assert (restored/'manifest.json').read_bytes()==original
    manifest['recipe']['implementation_sha256']='0'*64
    path.write_text(json.dumps(manifest),encoding='utf-8')
    # A valid archive/checksum must not make an unknown preparation recipe trusted.
    with pytest.raises(ValueError,match='recipe'):
        pack_dataset(root,tmp_path/'unknown.zip')


def test_verified_dataset_has_content_identity_separate_from_manifest_bytes(tmp_path):
    from test_supsign_training import prepare
    from scripts.supsign_training import verify_dataset
    _, root, _ = prepare(tmp_path)
    before=verify_dataset(root)
    path=root/'manifest.json';manifest=json.loads(path.read_text())
    manifest['source_summary']['root']='/different-colab-account/source.zip'
    path.write_text(json.dumps(manifest),encoding='utf-8')
    after=verify_dataset(root)
    assert before['manifest_sha256'] != after['manifest_sha256']
    assert before['dataset_content_sha256'] == after['dataset_content_sha256']
