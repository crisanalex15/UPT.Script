# UPT.Script (Quiz Solver)

## Hotkeys

| Combinație | Acțiune |
|------------|---------|
| `Ctrl+Shift+S` | Request din clipboard |
| `Ctrl+Alt+D` | Captură zonă → **OCR local** (rapid) → AI |
| `Ctrl+Shift+A` | Setare cheie API |

**Captură:** tragi dreptunghi → OCR extrage textul → model FAST. Dacă OCR eșuează, fallback automat la model VLM (imagine).

Setări OCR în `application_settings.json`:
- `capture_use_ocr` — activează OCR la captură
- `ocr_fallback_vlm` — trimite imaginea dacă OCR nu găsește text
- `ocr_min_chars` — minimum caractere pentru a folosi OCR

Prima rulare OCR descarcă modelul local (~10 MB). Instalează deps: `pip install -r requirements.txt`
