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
