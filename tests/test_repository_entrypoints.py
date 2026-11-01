def test_shared_and_staff_assets_preserve_legacy_static_urls(client):
    for old, new in [('auth.js','shared/auth.js'), ('theme.js','shared/theme.js'),
                     ('catalog.js','shared/catalog.js'), ('theme.css','shared/theme.css'),
                     ('management.js','staff/management.js'), ('management.css','staff/management.css')]:
        modern = client.get('/web/'+new)
        assert modern.status_code == 200
        assert client.get('/web/'+old).content == modern.content


def test_public_source_check_is_read_only_and_hides_secret_values(tmp_path):
    from scripts.check_public_source import inspect_paths
    (tmp_path/'README.md').write_text('token = '+('gh'+'p_'+'x'*40))
    (tmp_path/'mobile').mkdir(); (tmp_path/'mobile/main.dart').write_text('void main() {}')
    before={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    findings=inspect_paths(tmp_path,['README.md','mobile/main.dart','../private.env'])
    assert {f['path'] for f in findings} == {'README.md','../private.env'}
    assert 'x'*40 not in str(findings)
    assert before=={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_public_source_check_rejects_symlink_without_reading_private_target(tmp_path):
    import pytest
    from scripts.check_public_source import inspect_paths
    private=tmp_path/'outside.txt';private.write_text('private data')
    root=tmp_path/'source';root.mkdir()
    link=root/'README.md'
    try:
        link.symlink_to(private)
    except OSError:
        pytest.skip('Symlink creation requires OS permission')
    result=inspect_paths(root,['README.md'])
    assert result==[{'path':'README.md','reason':'symbolic or redirected source'}]
