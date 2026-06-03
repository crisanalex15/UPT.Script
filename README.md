# UPT.Script (Quiz Solver)

## Hotkeys

| Combinație | Acțiune |
|------------|---------|
| `Ctrl+Shift+S` | Request din clipboard |
| `Ctrl+Alt+D` | Captură zonă → alegi **Text OCR** sau **Imagine** |
| `Ctrl+Shift+A` | Setare cheie API |

## Captură (Ctrl+Alt+D)

1. Tragi dreptunghi pe ecran
2. Apare **Text OCR | Imagine**
   - **Text OCR** (sau tasta `T`) → OCR local → model FAST (rapid)
   - **Imagine** (sau tasta `I`) → trimite poza → model VLM
   - **Esc** = anulare

## Setări (`application_settings.json`)

| Cheie | Valori | Descriere |
|-------|--------|-----------|
| `capture_mode` | `ask` / `ocr` / `image` | `ask` = alegi după captură |
| `ocr_fallback_vlm` | true/false | Dacă OCR e gol, trimite imaginea |
| `ocr_min_chars` | număr | Minim caractere pentru OCR valid |

Deps OCR: `pip install -r requirements.txt`
