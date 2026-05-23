param(
    [string]$OutputPath = "..\clienteiro_public_clean",
    [switch]$InitGit
)

$ErrorActionPreference = "Stop"

$source = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dest = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)

if (Test-Path $dest) {
    throw "OutputPath ja existe: $dest. Escolha uma pasta nova para evitar sobrescrever arquivos."
}

New-Item -ItemType Directory -Path $dest | Out-Null

$dangerousPattern = '(^|/)(\.env$|.*\.db$|.*\.sqlite$|.*\.sqlite3$|.*\.pem$|.*\.key$|.*\.p12$|.*\.pfx$|credentials\.json$|auth\.json$|token\.json$|evolution\.env$|instance\.json$|qrcode.*\.png$|\.wwebjs_auth/|\.wwebjs_cache/|session/)'
$files = git -C $source ls-files --cached --others --exclude-standard

foreach ($file in $files) {
    $normalized = $file -replace '\\', '/'
    if ($normalized -match $dangerousPattern) {
        Write-Host "Ignorado por seguranca: $file"
        continue
    }

    $srcFile = Join-Path $source $file
    if (-not (Test-Path -LiteralPath $srcFile -PathType Leaf)) {
        continue
    }

    $dstFile = Join-Path $dest $file
    $dstDir = Split-Path -Parent $dstFile
    if ($dstDir -and -not (Test-Path -LiteralPath $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir | Out-Null
    }
    Copy-Item -LiteralPath $srcFile -Destination $dstFile
}

if ($InitGit) {
    Push-Location $dest
    try {
        git init
        git add .
        git status --short
        Write-Host ""
        Write-Host "Repositorio limpo inicializado em: $dest"
        Write-Host "Revise o status acima e rode os testes antes do primeiro commit."
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "Copia publica limpa criada em: $dest"
    Write-Host "Para inicializar Git depois: cd `"$dest`"; git init; git add ."
}
