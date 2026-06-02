# Rulează: powershell -ExecutionPolicy Bypass -File install_and_run.ps1

$ErrorActionPreference = "Stop"
$ApiKey = "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"
$RepoDir = Join-Path $HOME "UPT.Script"

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python lipseste. Instalez cu winget..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

if (-not (Test-Path $RepoDir)) {
    git clone https://github.com/crisanalex15/UPT.Script.git $RepoDir
} else {
    Write-Host "UPT.Script exista deja."
}
Set-Location $RepoDir

$venvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
    } elseif (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe") {
        & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
    } else {
        Write-Host "Python inca nu e in PATH. Inchide PowerShell, deschide din nou, ruleaza din nou scriptul."
        exit 1
    }
}

& $venvPython -m pip install -r requirements.txt
& $venvPython .\quiz_solver.py $ApiKey
