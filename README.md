# UPT.Script (Quiz Solver)

Overlay discret pe taskbar pentru întrebări de programare (NVIDIA API).

## Run and play (PC nou) — comenzi PowerShell

**O singură dată pe PC** (dacă `python` nu e găsit):

```powershell
winget install -e --id Python.Python.3.12
```

Închide și redeschide PowerShell, apoi:

```powershell
git clone https://github.com/crisanalex15/UPT.Script.git
cd "UPT.Script"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\quiz_solver.py "nvapi-CHEIA_TA"
```

Dacă `UPT.Script` există deja: `cd UPT.Script` + `git pull`, apoi aceleași comenzi de venv/pip/run.

## Hotkeys (implicit)

| Combinație | Acțiune |
|------------|---------|
| `Ctrl+Shift+A` | Setare cheie API (sesiune) |
| `Ctrl+Shift+S` | Trimite întrebarea din clipboard |

Setările sunt în `application_settings.json`.

## Fără fișier cheie

Poți porni cu cheia direct în comandă:

```bat
start.bat "nvapi-..."
```

## Notă

- `api_key.local` nu se urcă pe Git (este în `.gitignore`).
- Pe Windows, hotkey global poate necesita terminal **Run as administrator**.
