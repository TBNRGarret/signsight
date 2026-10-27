[CmdletBinding()]
param(
    [string]$DataRoot,
    [string]$PythonPath,
    [string]$BindAddress = '127.0.0.1',
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [string]$CertificatePath,
    [string]$PrivateKeyPath
)
$ErrorActionPreference = 'Stop'
if ([bool]$CertificatePath -ne [bool]$PrivateKeyPath) {
    throw 'Provide both -CertificatePath and -PrivateKeyPath for HTTPS.'
}
$tlsArguments = @()
if ($CertificatePath) {
    foreach ($path in @($CertificatePath, $PrivateKeyPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'TLS certificate/key file not found.' }
    }
    $tlsArguments = @('--ssl-certfile', (Resolve-Path -LiteralPath $CertificatePath).Path,
                      '--ssl-keyfile', (Resolve-Path -LiteralPath $PrivateKeyPath).Path)
}
$sourceRoot = Split-Path -Parent $PSScriptRoot
if (-not $DataRoot) { $DataRoot = $sourceRoot }
$DataRoot = [System.IO.Path]::GetFullPath($DataRoot)
if (-not $PythonPath) {
    $candidate = Join-Path $sourceRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $candidate) { $PythonPath = $candidate }
    else { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
}
$variables = @{
    DATABASE_URL = 'sqlite:///' + (Join-Path $DataRoot 'backend/signsight.db').Replace('\', '/')
    SIGNSIGHT_STORAGE_ROOT = Join-Path $DataRoot 'backend/uploads/images'
    SIGNSIGHT_YOLO_WEIGHTS = Join-Path $DataRoot 'ai_engine/checkpoints/detection/best.pt'
    SIGNSIGHT_CNN_WEIGHTS = Join-Path $DataRoot 'ai_engine/checkpoints/best_model.pth'
}
$previous = @{}
foreach ($name in $variables.Keys) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, $variables[$name], 'Process')
}
Push-Location $sourceRoot
try {
    & $PythonPath -m uvicorn backend.app.main:app --host $BindAddress --port $Port @tlsArguments
    if ($LASTEXITCODE -ne 0) { throw "Server exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
    foreach ($name in $variables.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
