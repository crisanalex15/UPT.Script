# UPT.Script (Quiz Solver)

Overlay discret pe taskbar pentru întrebări de programare (NVIDIA API).

## Run and play (PC nou) — comenzi PowerShell

Copiază tot conținutul din **`Linie`** în PowerShell (verifică Python, clone, venv, run).

Sau o singură comandă după clone:

```powershell
powershell -ExecutionPolicy Bypass -File install_and_run.ps1
```

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
