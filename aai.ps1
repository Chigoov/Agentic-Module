# ==============================================================================
# AUTONOMI AGENTIC ILMIAH (AAI) - Local Command Launcher
# ==============================================================================

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [string]$Command = "help",

    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$ArgsList
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repoRoot

function Show-Help {
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host " AUTONOMI AGENTIC ILMIAH (AAI) - Local Command Launcher" -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Penggunaan:" -ForegroundColor Yellow
    Write-Host "  aai <perintah> [argumen]"
    Write-Host "  .\aai.bat <perintah> [argumen]"
    Write-Host ""
    Write-Host "Daftar Perintah:" -ForegroundColor Yellow
    Write-Host "  check               Memeriksa kesiapan sistem dan konfigurasi (python -m src check)"
    Write-Host "  open                Membuka live monitor di browser (menjalankan server jika belum aktif)"
    Write-Host "  monitor             Menjalankan monitor server di terminal ini (port 8000)"
    Write-Host "  run <input.json>    Menjalankan alur Academic Writing Mode dari input JSON"
    Write-Host "  runs <input.json>   Melihat riwayat audit trail eksekusi proyek"
    Write-Host "  bundle <input.json> Mengekspor hasil run proyek ke berkas .zip mandiri"
    Write-Host "  help                Menampilkan pesan bantuan ini"
    Write-Host ""
    Write-Host "Contoh Cepat:" -ForegroundColor Green
    Write-Host "  .\aai.bat check"
    Write-Host "  .\aai.bat open"
    Write-Host "  .\aai.bat run input_edjust_mini.json"
    Write-Host "  .\aai.bat runs input_edjust_mini.json"
    Write-Host "  .\aai.bat bundle input_edjust_mini.json"
    Write-Host ""
}

function Test-AutonomiPort {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $client.Connect("127.0.0.1", 8000)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Open-LiveMonitor {
    $url = "http://127.0.0.1:8000"
    if (-not (Test-AutonomiPort)) {
        Write-Host "Monitor belum aktif. Memulai monitor server di background terminal..." -ForegroundColor Yellow
        $escapedRoot = $repoRoot.Replace("'", "''")
        Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location -LiteralPath '$escapedRoot'; python -m src monitor --port 8000"
        Start-Sleep -Seconds 2
    }
    Write-Host "Membuka browser ke $url ..." -ForegroundColor Green
    Start-Process $url
}

function Resolve-JsonFile([string]$fileArg, [string]$actionName) {
    if (-not $fileArg -or $fileArg.Trim() -eq "") {
        Write-Host "[ERROR] Perintah '$actionName' memerlukan argumen file <input.json>." -ForegroundColor Red
        Write-Host ""
        Write-Host "Contoh penggunaan:" -ForegroundColor Yellow
        Write-Host "  .\aai.bat $actionName input_edjust_mini.json" -ForegroundColor Yellow
        exit 1
    }

    $target = $fileArg
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        $cand = Join-Path $repoRoot $fileArg
        if (Test-Path -LiteralPath $cand -PathType Leaf) {
            $target = $cand
        }
    }

    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        Write-Host "[ERROR] File input JSON tidak ditemukan: '$fileArg'" -ForegroundColor Red
        Write-Host ""
        Write-Host "Contoh penggunaan:" -ForegroundColor Yellow
        Write-Host "  .\aai.bat $actionName input_edjust_mini.json" -ForegroundColor Yellow
        exit 1
    }

    return (Resolve-Path -LiteralPath $target).Path
}

switch ($Command.ToLowerInvariant()) {
    "check" {
        python -m src check
        exit $LASTEXITCODE
    }
    "open" {
        Open-LiveMonitor
        exit 0
    }
    "monitor" {
        python -m src monitor --port 8000 @ArgsList
        exit $LASTEXITCODE
    }
    "run" {
        $jsonTarget = Resolve-JsonFile ($ArgsList | Select-Object -First 1) "run"
        $remaining = @()
        if ($ArgsList.Count -gt 1) {
            $remaining = $ArgsList[1..($ArgsList.Count - 1)]
        }
        python -m src run-academic --input-json $jsonTarget @remaining
        exit $LASTEXITCODE
    }
    "runs" {
        $jsonTarget = Resolve-JsonFile ($ArgsList | Select-Object -First 1) "runs"
        $remaining = @()
        if ($ArgsList.Count -gt 1) {
            $remaining = $ArgsList[1..($ArgsList.Count - 1)]
        }
        python -m src runs --input-json $jsonTarget @remaining
        exit $LASTEXITCODE
    }
    "bundle" {
        $jsonTarget = Resolve-JsonFile ($ArgsList | Select-Object -First 1) "bundle"
        $remaining = @()
        if ($ArgsList.Count -gt 1) {
            $remaining = $ArgsList[1..($ArgsList.Count - 1)]
        }
        python -m src export-bundle --input-json $jsonTarget @remaining
        exit $LASTEXITCODE
    }
    "help" {
        Show-Help
        exit 0
    }
    default {
        Write-Host "[ERROR] Perintah '$Command' tidak dikenal." -ForegroundColor Red
        Write-Host ""
        Show-Help
        exit 1
    }
}
