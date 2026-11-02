"""Exercise launcher argument forwarding without starting a real server."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which('powershell') or shutil.which('pwsh')
pytestmark = pytest.mark.skipif(not SHELL, reason='PowerShell is not installed')


def test_https_launcher_forwards_both_tls_paths_and_keeps_external_runtime(tmp_path):
    mock = tmp_path / 'python mock.ps1'
    mock.write_text("""param([Parameter(ValueFromRemainingArguments=$true)]$Forwarded)
@{ arguments = $Forwarded; database = $env:DATABASE_URL; images = $env:SIGNSIGHT_STORAGE_ROOT } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $env:SIGNSIGHT_LAUNCH_TEST_OUTPUT
$global:LASTEXITCODE = 0
""", encoding='utf-8')
    cert, key = tmp_path/'cert.pem', tmp_path/'key.pem'
    cert.write_text('fixture certificate'); key.write_text('fixture key')
    output = tmp_path/'invocation.json'
    environment = dict(os.environ, SIGNSIGHT_LAUNCH_TEST_OUTPUT=str(output))
    result = subprocess.run([SHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(ROOT/'scripts/start_local.ps1'), '-DataRoot', str(tmp_path), '-PythonPath', str(mock),
        '-Port', '8443', '-CertificatePath', str(cert), '-PrivateKeyPath', str(key)],
        env=environment, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    invocation = json.loads(output.read_text(encoding='utf-8-sig'))
    assert invocation['database'] == 'sqlite:///' + str(tmp_path/'backend/signsight.db').replace('\\','/')
    assert invocation['arguments'][-4:] == ['--ssl-certfile', str(cert), '--ssl-keyfile', str(key)]


def test_https_launcher_rejects_an_incomplete_certificate_pair_before_starting(tmp_path):
    cert=tmp_path/'cert.pem';cert.write_text('fixture')
    mock=tmp_path/'forbidden.ps1';mock.write_text("throw 'Server must not start'")
    result=subprocess.run([SHELL,'-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(ROOT/'scripts/start_local.ps1'),'-CertificatePath',str(cert),'-PythonPath',str(mock)],capture_output=True,text=True,timeout=15)
    assert result.returncode != 0
    assert 'Provide both' in result.stderr


def test_launcher_applies_explicit_model_and_runtime_profile(tmp_path):
    mock = tmp_path/'python mock.ps1'
    mock.write_text("""param([Parameter(ValueFromRemainingArguments=$true)]$Forwarded)
@{ database = $env:DATABASE_URL; images = $env:SIGNSIGHT_STORAGE_ROOT;
weights = $env:SIGNSIGHT_YOLO_WEIGHTS; catalog = $env:SIGNSIGHT_CATALOG_PATH;
mapping = $env:SIGNSIGHT_YOLO_MAPPING_PATH; device = $env:SIGNSIGHT_YOLO_DEVICE;
confidence = $env:SIGNSIGHT_YOLO_CONFIDENCE } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $env:SIGNSIGHT_LAUNCH_TEST_OUTPUT
$global:LASTEXITCODE = 0
""", encoding='utf-8')
    values = dict(database_url='sqlite:///'+str(tmp_path/'copied/signsight.db').replace('\\','/'),
                  storage_root=str(tmp_path/'copied/images'), yolo_weights=str(tmp_path/'candidate/best.pt'),
                  catalog_path=str(tmp_path/'candidate/catalog.json'),
                  yolo_mapping_path=str(tmp_path/'candidate/mapping.json'), yolo_device='0', yolo_confidence=.35)
    profile=tmp_path/'profile.json'; profile.write_text(json.dumps(values),encoding='utf-8')
    output=tmp_path/'invocation.json'
    result=subprocess.run([SHELL,'-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(ROOT/'scripts/start_local.ps1'),'-DataRoot',str(tmp_path/'legacy'),'-PythonPath',str(mock),
        '-RuntimeProfile',str(profile)], env=dict(os.environ,SIGNSIGHT_LAUNCH_TEST_OUTPUT=str(output)),
        capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stderr
    actual=json.loads(output.read_text(encoding='utf-8-sig'))
    assert actual == dict(database=values['database_url'],images=values['storage_root'],
                          weights=values['yolo_weights'],catalog=values['catalog_path'],
                          mapping=values['yolo_mapping_path'],device='0',confidence='0.35')


def test_launcher_rejects_unknown_profile_fields_before_starting(tmp_path):
    profile=tmp_path/'profile.json'; profile.write_text(json.dumps({'unrecognized_setting':'x'}))
    mock=tmp_path/'forbidden.ps1'; mock.write_text("throw 'Server must not start'")
    result=subprocess.run([SHELL,'-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(ROOT/'scripts/start_local.ps1'),'-RuntimeProfile',str(profile),'-PythonPath',str(mock)],
        capture_output=True,text=True,timeout=15)
    assert result.returncode != 0
    assert 'Unknown runtime profile field' in result.stderr


@pytest.mark.parametrize('field,value', [('storage_root','relative-images'),('yolo_weights',''),('database_url',' ')])
def test_launcher_rejects_profile_values_that_could_fall_back_to_source_runtime(tmp_path, field, value):
    profile=tmp_path/'profile.json'; profile.write_text(json.dumps({field:value}))
    marker=tmp_path/'started.txt'
    mock=tmp_path/'python mock.ps1'
    mock.write_text("'started' | Set-Content -LiteralPath $env:SIGNSIGHT_LAUNCH_TEST_OUTPUT\n$global:LASTEXITCODE=0")
    result=subprocess.run([SHELL,'-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(ROOT/'scripts/start_local.ps1'),'-RuntimeProfile',str(profile),'-PythonPath',str(mock)],
        env=dict(os.environ,SIGNSIGHT_LAUNCH_TEST_OUTPUT=str(marker)),capture_output=True,text=True,timeout=15)
    assert result.returncode != 0
    assert 'Invalid runtime profile value' in result.stderr
    assert not marker.exists()
