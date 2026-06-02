# UPT.Script (Quiz Solver)

Overlay discret pe taskbar pentru întrebări de programare (NVIDIA API).

## PC nou (de la zero) — o singură comandă

Deschide **PowerShell** și lipește:

```powershell
irm https://raw.githubusercontent.com/crisanalex15/UPT.Script/main/fresh_pc.ps1 | iex
```

Scriptul instalează automat (dacă lipsesc) **Git** și **Python**, clonează repo-ul, creează `.venv`, instalează dependențele și pornește aplicația.

Dacă după prima rulare cere repornire terminal: închide PowerShell, deschide din nou, rulează aceeași comandă.

## Hotkeys (implicit)

| Combinație | Acțiune |
|------------|---------|
| `Ctrl+Shift+A` | Setare cheie API (sesiune) |
| `Ctrl+Shift+S` | Trimite întrebarea din clipboard |

Setările sunt în `application_settings.json`.

## Notă

- Pe Windows, hotkey global poate necesita terminal **Run as administrator**.
