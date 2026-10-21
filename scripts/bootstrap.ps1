# Создаёт .env из .env.example со случайными паролями и JWT-секретом (E02-06.6).
# Шаг необязательный: без .env стенд поднимается на учебных значениях по умолчанию (NFR-01).
# Запускайте до первого `make up`: пароли PostgreSQL и MinIO запоминаются в томах при первом старте.
# Использование: scripts\bootstrap.ps1 [-Force] [-Output ФАЙЛ]
param(
    [switch]$Force,
    [string]$Output = ".env"
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$target = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $root $Output }

if ((Test-Path $target) -and -not $Force) {
    Write-Output "$target уже существует — оставляю без изменений (-Force перезапишет)."
    exit 0
}

function New-RandomHex([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($buffer)
    $rng.Dispose()
    return ([System.BitConverter]::ToString($buffer) -replace "-", "").ToLower()
}

$values = @{
    POSTGRES_PASSWORD   = New-RandomHex 16
    DB_CORE_PASSWORD    = New-RandomHex 16
    DB_KB_PASSWORD      = New-RandomHex 16
    DB_BANK_PASSWORD    = New-RandomHex 16
    DB_ML_PASSWORD      = New-RandomHex 16
    DB_DOCS_PASSWORD    = New-RandomHex 16
    MINIO_ROOT_PASSWORD = New-RandomHex 16
    JWT_SECRET          = New-RandomHex 32
}

$template = Get-Content -Encoding UTF8 (Join-Path $root ".env.example")
foreach ($name in $values.Keys) {
    if (-not ($template | Where-Object { $_.StartsWith("$name=") })) {
        throw "В .env.example нет переменной $name"
    }
}
$lines = $template | ForEach-Object {
    $line = $_
    foreach ($name in $values.Keys) {
        if ($line.StartsWith("$name=")) { $line = "$name=$($values[$name])" }
    }
    $line
}
# UTF-8 без BOM: docker compose читает .env как есть
[System.IO.File]::WriteAllLines($target, $lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "Создан $target со случайными паролями и JWT-секретом."

if (Get-Command docker -ErrorAction SilentlyContinue) {
    $volumes = docker volume ls -q 2>$null
    if ($volumes -match "^cabinet_(postgres|minio)-data$") {
        Write-Warning ("Тома стенда уже существуют, а пароли PostgreSQL и MinIO в них заданы при первом " +
            "старте. Чтобы новые пароли заработали: make down; docker volume rm " +
            "cabinet_postgres-data cabinet_minio-data (данные будут удалены).")
    }
}
