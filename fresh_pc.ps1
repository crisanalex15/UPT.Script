# PC nou de la zero: Git + Python (daca lipsesc) + clone + run
$ErrorActionPreference = "Continue"
$ApiKey = "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"
$RepoDir = Join-Path $HOME "UPT.Script"

function Refresh-PathEnv {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Ensure-Winget {
    if (Get-Command winget -ErrorAction SilentlyContinue) { return $true }
    Write-Host "winget lipseste. Instaleaza App Installer din Microsoft Store, apoi ruleaza din nou."
    return $false
}

function New-Venv {
    param([string]$TargetDir)
    Set-Location $TargetDir
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
        return
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
        return
    }
    $fallback = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (Test-Path $fallback) {
        & $fallback -m venv .venv
        return
    }
    throw "Python nu e disponibil. Inchide PowerShell, deschide din nou, ruleaza din nou scriptul."
}

if (-not (Ensure-Winget)) { exit 1 }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[1/4] Instalez Git..."
    winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
    Refresh-PathEnv
}

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "[2/4] Instalez Python..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    Refresh-PathEnv
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git inca lipseste. Reporneste PowerShell si ruleaza din nou."
    exit 1
}

if (-not (Test-Path $RepoDir)) {
    Write-Host "[3/4] Clonez repo..."
    git clone https://github.com/crisanalex15/UPT.Script.git $RepoDir
} else {
    Write-Host "[3/4] Repo exista, continui..."
}

$venvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[4/4] Creez mediul virtual..."
    New-Venv -TargetDir $RepoDir
}

Write-Host "Pornesc Quiz Solver..."
Set-Location $RepoDir
& $venvPython -m pip install -r requirements.txt -q
& $venvPython .\quiz_solver.py $ApiKey
