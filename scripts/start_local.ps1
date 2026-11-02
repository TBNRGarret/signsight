[CmdletBinding()]
param(
    [string]$DataRoot,
    [string]$PythonPath,
    [string]$RuntimeProfile,
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
}
if ($RuntimeProfile) {
    $profileFields = @{
        database_url = 'DATABASE_URL'
        storage_root = 'SIGNSIGHT_STORAGE_ROOT'
        yolo_weights = 'SIGNSIGHT_YOLO_WEIGHTS'
        catalog_path = 'SIGNSIGHT_CATALOG_PATH'
        yolo_mapping_path = 'SIGNSIGHT_YOLO_MAPPING_PATH'
        yolo_device = 'SIGNSIGHT_YOLO_DEVICE'
        yolo_confidence = 'SIGNSIGHT_YOLO_CONFIDENCE'
    }
    if (-not (Test-Path -LiteralPath $RuntimeProfile -PathType Leaf)) { throw 'Runtime profile file not found.' }
    $profile = Get-Content -LiteralPath $RuntimeProfile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $profile -or $profile -is [Array] -or $profile -is [String]) { throw 'Runtime profile must be a JSON object.' }
    foreach ($property in $profile.PSObject.Properties) {
        if (-not $profileFields.ContainsKey($property.Name)) { throw "Unknown runtime profile field: $($property.Name)" }
        if ($null -eq $property.Value -or -not ($property.Value -is [String] -or $property.Value -is [ValueType])) {
            throw 'Runtime profile values must be scalar strings or numbers.'
        }
        $value = [Convert]::ToString($property.Value, [Globalization.CultureInfo]::InvariantCulture)
        if ($property.Name -in @('storage_root','yolo_weights','catalog_path','yolo_mapping_path')) {
            if ([String]::IsNullOrWhiteSpace($value)) {
                throw "Invalid runtime profile value: $($property.Name) requires an absolute path."
            }
            $root = [IO.Path]::GetPathRoot($value)
            if (-not [IO.Path]::IsPathRooted($value) -or
                ([IO.Path]::DirectorySeparatorChar -eq '\' -and $root.Length -lt 3)) {
                throw "Invalid runtime profile value: $($property.Name) requires an absolute path."
            }
        } elseif ($property.Name -eq 'database_url' -and [String]::IsNullOrWhiteSpace($value)) {
            throw 'Invalid runtime profile value: database_url must not be blank.'
        }
        $variables[$profileFields[$property.Name]] = $value
    }
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
