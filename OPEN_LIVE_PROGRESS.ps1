$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$url = "http://127.0.0.1:8000"

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

if (-not (Test-AutonomiPort)) {
    $escapedRoot = $root.Replace("'", "''")
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location -LiteralPath '$escapedRoot'; python -m src monitor --port 8000"
    Start-Sleep -Seconds 2
}

Start-Process $url
