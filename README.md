# UPT.Script (Quiz Solver)

Overlay discret pe taskbar pentru întrebări de programare (NVIDIA API).

## Run and play (PC nou)

1. Clonează repo-ul:

```powershell
git clone https://github.com/crisanalex15/UPT.Script.git
cd UPT.Script
```

2. Dublu-click pe **`setup.bat`** (o singură dată) — instalează Python dacă lipsește, creează `.venv`, instalează pachetele.

3. Copiază `api_key.local.example` → `api_key.local` și pune cheia ta `nvapi-...` pe prima linie.

4. Dublu-click pe **`start.bat`** — pornește aplicația.

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
