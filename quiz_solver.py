#!/usr/bin/env python3
"""
Quiz Solver — overlay discret pe taskbar, alimentat de NVIDIA NIM API.

Instalare:
    pip install -r requirements.txt

Configurare:
    Editează application_settings.json pentru setările aplicației.
    Setează cheia NVIDIA doar în runtime (Ctrl+Shift+A), pentru sesiunea curentă.

Utilizare:
    1. Rulează: python quiz_solver.py
       sau:    python quiz_solver.py "<NVIDIA_API_KEY>"
    2. Selectează întrebarea (grilă SAU răspuns deschis), copiază (Ctrl+C)
    3. Ctrl+Shift+S = request din clipboard | Ctrl+Alt+D = captură zonă (chenar punctat)
    4. Pe taskbar apare un indiciu scurt; click Copy pentru textul complet de lipit
    5. Click dreapta pe widget → Exit

Suportă:
    - Grilă (A/B/C/D, True/False) → Copy = textul opțiunii corecte
    - Răspuns deschis (completare, short answer) → Copy = răspunsul gata de trimis

Notă Windows: biblioteca `keyboard` poate necesita rulare ca Administrator
pentru hotkey global.
"""

from __future__ import annotations

from collections.abc import Callable
import base64
import io
import json
import math
import os
import re
import signal
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import simpledialog

import keyboard
import pyperclip
from openai import APIStatusError, OpenAI, RateLimitError

# ---------------------------------------------------------------------------
# Configurare — application settings (JSON)
# ---------------------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_SETTINGS_FILE = os.path.join(APP_DIR, "application_settings.json")

DEFAULT_SETTINGS: dict[str, object] = {
    "nvidia_api_key": "",
    "nvidia_base_url": "https://integrate.api.nvidia.com/v1",
    "nvidia_model_fast": "meta/llama-3.3-70b-instruct",
    "nvidia_model_vlm": "mistralai/mistral-large-3-675b-instruct-2512",
    "hotkey_request": "ctrl+shift+s",
    "hotkey_capture": "ctrl+alt+d",
    "hotkey_set_api_key": "ctrl+shift+a",
    "api_min_interval_sec": 2.0,
    "api_max_retries": 2,
    "api_retry_base_sec": 3.0,
    "api_max_output_tokens": 400,
    "api_max_output_short": 320,
    "api_max_output_long": 520,
    "api_max_output_code": 4096,
    "image_max_dimension_px": 400,
    "image_jpeg_quality": 65,
}


def _load_app_settings() -> dict[str, object]:
    try:
        with open(APP_SETTINGS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
    except Exception:
        pass
    return dict(DEFAULT_SETTINGS)


_SETTINGS = _load_app_settings()


def _setting_str(key: str) -> str:
    value = _SETTINGS.get(key, DEFAULT_SETTINGS[key])
    return str(value).strip()


def _setting_int(key: str) -> int:
    value = _SETTINGS.get(key, DEFAULT_SETTINGS[key])
    try:
        return int(value)
    except Exception:
        return int(DEFAULT_SETTINGS[key])


def _setting_float(key: str) -> float:
    value = _SETTINGS.get(key, DEFAULT_SETTINGS[key])
    try:
        return float(value)
    except Exception:
        return float(DEFAULT_SETTINGS[key])


NVIDIA_API_KEY: str = _setting_str("nvidia_api_key")
NVIDIA_BASE_URL: str = _setting_str("nvidia_base_url") or str(DEFAULT_SETTINGS["nvidia_base_url"])
NVIDIA_MODEL_VLM: str = _setting_str("nvidia_model_vlm") or str(DEFAULT_SETTINGS["nvidia_model_vlm"])
NVIDIA_MODEL_FAST: str = _setting_str("nvidia_model_fast") or str(DEFAULT_SETTINGS["nvidia_model_fast"])
API_MAX_RETRIES: int = max(1, min(3, _setting_int("api_max_retries")))
API_RETRY_BASE_SEC: float = max(0.5, _setting_float("api_retry_base_sec"))
API_RETRYABLE_STATUS: frozenset[int] = frozenset({500, 502, 503, 504})
API_MAX_OUTPUT_TOKENS: int = max(128, _setting_int("api_max_output_tokens"))
API_MAX_OUTPUT_SHORT: int = max(180, _setting_int("api_max_output_short"))
API_MAX_OUTPUT_CODE: int = max(1024, _setting_int("api_max_output_code"))
API_MAX_OUTPUT_LONG: int = max(300, _setting_int("api_max_output_long"))
IMAGE_MAX_DIMENSION_PX: int = max(64, _setting_int("image_max_dimension_px"))
IMAGE_JPEG_QUALITY: int = max(30, min(95, _setting_int("image_jpeg_quality")))
HOTKEY: str = _setting_str("hotkey_request").lower() or "ctrl+shift+s"
HOTKEY_CAPTURE: str = _setting_str("hotkey_capture").lower() or "ctrl+alt+d"
HOTKEY_SET_API_KEY: str = _setting_str("hotkey_set_api_key").lower() or "ctrl+shift+a"
API_MIN_INTERVAL_SEC: float = max(2.0, _setting_float("api_min_interval_sec"))

# Mesaje fără buton Copy (doar feedback pe taskbar)
NO_COPY_DISPLAYS: frozenset[str] = frozenset(
    {
        "?",
        "...",
        "…+📷",
        "Nimic copiat",
        "Fără cheie API",
        "Prea rapid",
        "Limită/min (429)",
        "Cotă epuizată",
        "Limită/zi",
        "Cheie API invalidă",
        "Cerere invalidă",
        "Server ocupat",
        "Server 503",
        "Reîncerc…",
        "Fără răspuns",
        "Eroare rețea",
        "Eroare API",
        "Cod lipsă?",
    }
)

TASKBAR_BG = "#101010"
TEXT_COLOR = "#E8E8E8"
BUTTON_BG = "#252525"
BUTTON_FG = "#AAAAAA"
BUTTON_ACTIVE = "#353535"
# Culoare-cheie folosită pentru transparență pe Windows (transparentcolor).
TRANSPARENT_KEY = "#010203"
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 9
DISPLAY_MAX_CHARS = 22
WINDOW_POS_FILE = os.path.join(
    APP_DIR,
    ".quiz_solver_window_pos.json",
)

SYSTEM_PROMPT = (
    "Ești un asistent tehnic pentru întrebări de programare (algoritmi, Python, C/C++, Java, SQL, Bash, Linux, OOP, structuri de date).\n"
    "Răspunzi strict în format parsabil.\n\n"
    "FORMAT OBLIGATORIU:\n"
    "1) Dacă întrebarea este grilă (A/B/C/D/E, True/False), răspunsul trebuie să fie PE O SINGURĂ LINIE:\n"
    "MCQ|||[număr întrebare]. [literă]|||[literă]\n"
    "Exemplu: MCQ|||5. B|||B\n"
    "Nu scrie textul opțiunii, nu explicație.\n\n"
    "2) Dacă întrebarea este deschisă, răspunsul începe cu:\n"
    "OPEN|||[număr întrebare]. [hint scurt]|||[răspuns]\n"
    "Pentru cod, după antet pui codul complet (fără ```).\n\n"
    "Reguli stricte:\n"
    "- Niciun text în afara formatului.\n"
    "- Dacă detectezi OCR/typo, corectează logic intern, dar păstrează formatul.\n"
)

# Dimensiuni overlay taskbar (zona liberă = între iconițe și tray/ceas)
# Langa ceas
STRIP_HEIGHT = 26
STRIP_MIN_WIDTH = 90
STRIP_MAX_WIDTH = 280

# Proporții din lățimea ecranului — potrivite pentru taskbar centrat (Win11)
TASKBAR_ICONS_FRACTION = 0.32
TASKBAR_TRAY_FRACTION = 0.22
TASKBAR_HEIGHT_PX = 48

# Selector zonă ecran — chenar punctat; alpha mic (NU transparentcolor: click-urile trec prin)
CAPTURE_BORDER_COLOR = "#00A8FF"
CAPTURE_HINT_COLOR = "#FFFFFF"
CAPTURE_MIN_SIZE_PX = 10
CAPTURE_OVERLAY_ALPHA = 0.08


class RegionSelectOverlay:
    """Fullscreen aproape invizibil; la drag apare chenar punctat. Primește click-uri."""

    def __init__(
        self,
        root: tk.Tk,
        on_complete: Callable[[bytes | None], None],
    ) -> None:
        self.root = root
        self.on_complete = on_complete
        self._start_x = 0
        self._start_y = 0
        self._rect_id: int | None = None
        self._closed = False

        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)

        try:
            sw = root.winfo_vrootwidth()
            sh = root.winfo_vrootheight()
            vx = root.winfo_vrootx()
            vy = root.winfo_vrooty()
        except tk.TclError:
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            vx = vy = 0
        self.top.geometry(f"{sw}x{sh}+{vx}+{vy}")

        # transparentcolor = click-through pe Windows; folosim alpha foarte mic
        overlay_bg = "#000000"
        self.top.configure(bg=overlay_bg)
        self.top.attributes("-alpha", CAPTURE_OVERLAY_ALPHA)

        self.canvas = tk.Canvas(
            self.top,
            bg=overlay_bg,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.create_text(
            16,
            16,
            text="Trage zona întrebării  •  Esc = anulare",
            anchor="nw",
            fill=CAPTURE_HINT_COLOR,
            font=(FONT_FAMILY, 10, "bold"),
        )

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.top.bind("<Escape>", self._on_cancel)
        self.top.bind("<Button-3>", self._on_cancel)
        self.top.bind("<KeyPress-Escape>", self._on_cancel)

        self.top.update_idletasks()
        self.top.deiconify()
        self.top.lift()
        self.top.focus_force()
        try:
            self.top.grab_set()
        except tk.TclError:
            pass
        print("[Capture] Selector activ — trage dreptunghi pe ecran.")

    def _canvas_xy(self, x_root: int, y_root: int) -> tuple[int, int]:
        return x_root - self.top.winfo_rootx(), y_root - self.top.winfo_rooty()

    def _on_press(self, event: tk.Event) -> None:
        self._start_x = event.x_root
        self._start_y = event.y_root
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
        cx, cy = self._canvas_xy(event.x_root, event.y_root)
        self._rect_id = self.canvas.create_rectangle(
            cx,
            cy,
            cx,
            cy,
            outline=CAPTURE_BORDER_COLOR,
            width=3,
            dash=(8, 4),
        )

    def _on_drag(self, event: tk.Event) -> None:
        if self._rect_id is None:
            return
        x0, y0 = self._canvas_xy(
            min(self._start_x, event.x_root),
            min(self._start_y, event.y_root),
        )
        x1, y1 = self._canvas_xy(
            max(self._start_x, event.x_root),
            max(self._start_y, event.y_root),
        )
        self.canvas.coords(self._rect_id, x0, y0, x1, y1)

    def _on_release(self, event: tk.Event) -> None:
        x1 = min(self._start_x, event.x_root)
        y1 = min(self._start_y, event.y_root)
        x2 = max(self._start_x, event.x_root)
        y2 = max(self._start_y, event.y_root)
        if x2 - x1 < CAPTURE_MIN_SIZE_PX or y2 - y1 < CAPTURE_MIN_SIZE_PX:
            self._close()
            self.on_complete(None)
            return
        bbox = (x1, y1, x2, y2)
        self._close()
        self.root.after(80, lambda: self._grab_bbox(bbox))

    def _grab_bbox(self, bbox: tuple[int, int, int, int]) -> None:
        try:
            from PIL import ImageGrab

            img = ImageGrab.grab(bbox=bbox)
            jpeg = _compress_clipboard_image(img)
            self.on_complete(jpeg)
        except Exception as exc:
            print(f"[Capture] Eroare: {exc}")
            self.on_complete(None)

    def _on_cancel(self, _event: tk.Event | None = None) -> None:
        self._close()
        self.on_complete(None)

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.top.grab_release()
        except tk.TclError:
            pass
        try:
            self.top.destroy()
        except tk.TclError:
            pass


def _api_key_looks_valid(key: str) -> bool:
    key = key.strip()
    return bool(key) and key.startswith("nvapi-")


def _api_key_format_hint(key: str) -> str | None:
    key = key.strip()
    if not key:
        return "Cheia NVIDIA lipsește"
    if _api_key_looks_valid(key):
        return None
    return "Cheia NVIDIA nu pare validă. Cheia de la build.nvidia.com începe cu nvapi-"


def _hotkey_uses_function_key(hotkey: str) -> bool:
    return bool(re.search(r"(?:^|\+)f\d{1,2}(?:\+|$)", hotkey, re.IGNORECASE))


def _quota_exhausted(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "limit: 0" in msg:
        return True
    if "quota exceeded" in msg and "free_tier" in msg:
        return True
    if "exceeded your current quota" in msg:
        return True
    return False


def _is_retryable_api_error(exc: BaseException) -> bool:
    if _quota_exhausted(exc):
        return False
    if isinstance(exc, RateLimitError):
        return False
    if isinstance(exc, APIStatusError):
        if exc.status_code == 429:
            return False
        return exc.status_code in API_RETRYABLE_STATUS
    msg = str(exc).lower()
    if "429" in msg or "rate limit" in msg:
        return False
    return "503" in msg or "unavailable" in msg


def _read_clipboard_payload() -> tuple[str, bytes | None]:
    """Text + imagine din clipboard. Dacă există imagine, o trimitem mereu (textul poate fi vechi)."""
    raw = pyperclip.paste()
    text = raw.strip() if isinstance(raw, str) else ""

    image_jpeg: bytes | None = None
    try:
        from PIL import Image, ImageGrab

        clip = ImageGrab.grabclipboard()
        if clip is None:
            return text, None
        if isinstance(clip, Image.Image):
            image_jpeg = _compress_clipboard_image(clip)
        elif isinstance(clip, list) and clip:
            first = clip[0]
            if isinstance(first, str) and os.path.isfile(first):
                with Image.open(first) as img:
                    image_jpeg = _compress_clipboard_image(img)
    except Exception as exc:
        print(f"[Clipboard] Imagine ignorată: {exc}")

    if image_jpeg:
        if text:
            print("[Clipboard] Imagine + text (prioritate imagine; ignoră text vechi dacă diferă).")
        else:
            print("[Clipboard] Doar imagine din clipboard.")
        return text, image_jpeg

    return text, None


def _pick_nvidia_model(image_jpeg: bytes | None) -> str:
    if image_jpeg:
        return NVIDIA_MODEL_VLM
    return NVIDIA_MODEL_FAST


def _compress_clipboard_image(img: object) -> bytes | None:
    from PIL import Image

    if not isinstance(img, Image.Image):
        return None

    gray = img.convert("L")

    width, height = gray.size
    longest = max(width, height)
    if longest > IMAGE_MAX_DIMENSION_PX:
        scale = IMAGE_MAX_DIMENSION_PX / longest
        gray = gray.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )

    buffer = io.BytesIO()
    gray.save(buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def _create_nvidia_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def _build_chat_messages(question_text: str, image_jpeg: bytes | None) -> list[dict[str, object]]:
    if image_jpeg:
        prompt = (
            "Întrebarea este în imagine. Răspunde DOAR la ce se cere acolo. "
            "Ignoră orice text din clipboard care nu corespunde imaginii.\n"
        )
        if question_text:
            prompt += f"(Text din clipboard — folosește doar dacă coincide cu imaginea): {question_text}"
    else:
        prompt = question_text or "Read the quiz question and answer using the required format."
    if image_jpeg:
        b64 = base64.b64encode(image_jpeg).decode("ascii")
        user_content: list[dict[str, object]] | str = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
        ]
    else:
        user_content = prompt

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _max_output_tokens_for(
    question_text: str, image_jpeg: bytes | None = None
) -> int:
    if image_jpeg:
        return API_MAX_OUTPUT_CODE
    if QuizSolverApp._looks_like_code_question(question_text):
        return API_MAX_OUTPUT_CODE
    if QuizSolverApp._looks_like_mcq(question_text):
        return min(API_MAX_OUTPUT_TOKENS, 128)
    if QuizSolverApp._looks_like_short_definition(question_text):
        return API_MAX_OUTPUT_SHORT
    if QuizSolverApp._looks_like_open_explanation(question_text):
        return API_MAX_OUTPUT_LONG
    return API_MAX_OUTPUT_TOKENS


def _generate_nvidia_with_retry(
    client: OpenAI,
    question_text: str,
    image_jpeg: bytes | None = None,
    *,
    status_callback: Callable[[int, float, str], None] | None = None,
) -> str:
    """Apel NVIDIA NIM (OpenAI-compatible); reîncearcă doar la erori 5xx."""
    last_exc: BaseException | None = None
    max_tokens = _max_output_tokens_for(question_text, image_jpeg)
    messages = _build_chat_messages(question_text, image_jpeg)
    model = _pick_nvidia_model(image_jpeg)

    for attempt in range(API_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.1,
            )
            content = response.choices[0].message.content
            return (content or "").strip()
        except Exception as exc:
            last_exc = exc
            if not _is_retryable_api_error(exc):
                raise
            if attempt >= API_MAX_RETRIES - 1:
                raise
            wait_sec = API_RETRY_BASE_SEC * (2**attempt)
            if status_callback is not None:
                status_callback(attempt + 1, wait_sec, model)
            time.sleep(wait_sec)

    if last_exc is not None:
        raise last_exc
    return ""


def _api_error_display(exc: BaseException) -> str:
    """Mesaj scurt pentru taskbar din excepția NVIDIA/OpenAI."""
    if isinstance(exc, RateLimitError) or (
        isinstance(exc, APIStatusError) and exc.status_code == 429
    ):
        if _quota_exhausted(exc):
            return "Cotă epuizată"
        return "Limită/min (429)"

    if isinstance(exc, APIStatusError):
        code = exc.status_code
        if code in (401, 403):
            return "Cheie API invalidă"
        if code == 400:
            return "Cerere invalidă"
        if code == 404:
            return "Model indisponibil"
        if code == 503:
            return "Server 503"
        if code in API_RETRYABLE_STATUS:
            return "Server ocupat"
        return f"Eroare API ({code})"

    msg = str(exc).lower()
    if "503" in msg or "unavailable" in msg:
        return "Server 503"
    if "429" in msg or "rate limit" in msg:
        return "Limită/min (429)"
    if "401" in msg or "403" in msg:
        return "Cheie API invalidă"
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "Eroare rețea"

    return "Eroare API"


class QuizSolverApp:
    """Aplicație frameless, always-on-top, integrată vizual în taskbar."""

    def __init__(self, initial_api_key: str = "") -> None:
        self.root = tk.Tk()
        self.root.title("Quiz Solver")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self._chrome_bg = TASKBAR_BG
        self.root.configure(bg=TASKBAR_BG)
        # Fundal transparent: păstrăm vizibile doar textul și butonul.
        if sys.platform.startswith("win"):
            try:
                self.root.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
                self.root.configure(bg=TRANSPARENT_KEY)
                self._chrome_bg = TRANSPARENT_KEY
            except tk.TclError:
                self._chrome_bg = TASKBAR_BG

        self._busy = False
        self._fade_job: str | None = None
        self._last_clipboard = ""
        self._last_display = ""
        self._last_copy_text = ""
        self._last_api_call: float = 0.0
        self._shutdown_requested = False
        self._shutting_down = False
        self._dragging = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._drag_start_x_root = 0
        self._drag_start_y_root = 0
        self._drag_moved = False
        self._manual_position: tuple[int, int] | None = self._load_saved_position()
        self._session_api_key: str = initial_api_key.strip()
        self._api_prompt_open = False
        self._region_select_active = False

        self._setup_ui()
        self._setup_context_menu()
        self._position_window()
        self._register_hotkey()
        self._install_ctrl_c_handler()

        self.root.withdraw()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        self.frame = tk.Frame(self.root, bg=self._chrome_bg, padx=6, pady=2)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.label_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE)
        self.button_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE - 1)

        self.status_label = tk.Label(
            self.frame,
            text="",
            bg=self._chrome_bg,
            fg=TEXT_COLOR,
            font=self.label_font,
            anchor="w",
        )
        self.status_label.pack(side=tk.LEFT, padx=(0, 4))

        self.copy_btn = tk.Button(
            self.frame,
            text="Copy",
            command=self._on_copy_clicked,
            bg=BUTTON_BG,
            fg=BUTTON_FG,
            activebackground=BUTTON_ACTIVE,
            activeforeground=TEXT_COLOR,
            relief=tk.FLAT,
            bd=0,
            padx=4,
            pady=0,
            font=self.button_font,
            cursor="hand2",
        )
        self.copy_btn.pack(side=tk.LEFT)
        self.copy_btn.pack_forget()

    def _setup_context_menu(self) -> None:
        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#1E1E1E", fg=TEXT_COLOR)
        self.context_menu.add_command(label="Exit", command=self._exit_app)

        for widget in (self.root, self.frame, self.status_label, self.copy_btn):
            widget.bind("<Button-3>", self._show_context_menu)

        # Drag pe click stânga: mută overlay-ul oriunde pe ecran.
        # Includem inclusiv butonul Copy; click simplu rămâne copy,
        # iar dacă utilizatorul trage, evităm acțiunea de copiere.
        for widget in (self.root, self.frame, self.status_label, self.copy_btn):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)

    def _show_context_menu(self, event: tk.Event) -> None:
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _start_drag(self, event: tk.Event) -> None:
        self._dragging = True
        self._drag_moved = False
        self._drag_start_x_root = event.x_root
        self._drag_start_y_root = event.y_root
        self._drag_offset_x = event.x_root - self.root.winfo_x()
        self._drag_offset_y = event.y_root - self.root.winfo_y()

    def _on_drag(self, event: tk.Event) -> None:
        if not self._dragging:
            return
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = self.root.winfo_width()
        height = self.root.winfo_height()

        x = event.x_root - self._drag_offset_x
        y = event.y_root - self._drag_offset_y
        moved_x = abs(event.x_root - self._drag_start_x_root)
        moved_y = abs(event.y_root - self._drag_start_y_root)
        if moved_x >= 3 or moved_y >= 3:
            self._drag_moved = True

        # Clamp în ecran ca să nu se piardă widget-ul complet în afara desktop-ului.
        x = max(0, min(x, max(0, screen_w - width)))
        y = max(0, min(y, max(0, screen_h - height)))
        self.root.geometry(f"+{x}+{y}")

    def _stop_drag(self, _event: tk.Event) -> None:
        self._dragging = False
        if self._drag_moved:
            self._manual_position = (self.root.winfo_x(), self.root.winfo_y())
            self._save_manual_position()

    def _taskbar_center_x(self, width: int) -> int:
        """Centrare în banda liberă a taskbar-ului (între app-uri și tray/ceas)."""
        screen_w = self.root.winfo_screenwidth()
        left_edge = int(screen_w * TASKBAR_ICONS_FRACTION)
        right_edge = screen_w - int(screen_w * TASKBAR_TRAY_FRACTION)
        slot = right_edge - left_edge
        if slot <= width:
            return max(0, (screen_w - width) // 2)
        return left_edge + (slot - width) // 2

    def _position_window(self) -> None:
        self.root.update_idletasks()
        width = min(
            STRIP_MAX_WIDTH,
            max(STRIP_MIN_WIDTH, self.frame.winfo_reqwidth() + 8),
        )
        height = STRIP_HEIGHT

        screen_h = self.root.winfo_screenheight()
        screen_w = self.root.winfo_screenwidth()

        if self._manual_position is not None:
            x, y = self._manual_position
            x = max(0, min(x, max(0, screen_w - width)))
            y = max(0, min(y, max(0, screen_h - height)))
            self._manual_position = (x, y)
        else:
            x = self._taskbar_center_x(width)
            y = screen_h - TASKBAR_HEIGHT_PX + (TASKBAR_HEIGHT_PX - height) // 2

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------------
    # Hotkey & workflow
    # ------------------------------------------------------------------
    def _register_hotkey(self) -> None:
        # F10 singur e captat de Windows/browser; cu Ctrl/Shift merge global
        suppress = _hotkey_uses_function_key(HOTKEY) and "+" not in HOTKEY.replace(" ", "")
        try:
            keyboard.add_hotkey(HOTKEY, self._on_hotkey_pressed, suppress=suppress)
        except Exception as exc:
            raise RuntimeError(
                f"Nu s-a putut înregistra hotkey-ul '{HOTKEY}'. "
                "Verifică hotkey_request în application_settings.json sau rulează terminalul ca Administrator."
            ) from exc
        try:
            keyboard.add_hotkey(HOTKEY_SET_API_KEY, self._on_api_hotkey_pressed, suppress=False)
        except Exception as exc:
            raise RuntimeError(
                f"Nu s-a putut înregistra hotkey-ul '{HOTKEY_SET_API_KEY}' pentru API key."
            ) from exc
        try:
            keyboard.add_hotkey(
                HOTKEY_CAPTURE,
                self._on_capture_hotkey_pressed,
                suppress=True,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Nu s-a putut înregistra hotkey-ul '{HOTKEY_CAPTURE}' pentru captură zonă."
            ) from exc
        print(
            f"[Hotkeys] Request={HOTKEY} | Captură={HOTKEY_CAPTURE} | API key={HOTKEY_SET_API_KEY}"
        )

    def _on_hotkey_pressed(self) -> None:
        self.root.after(0, self._handle_hotkey)

    def _on_capture_hotkey_pressed(self) -> None:
        print(f"[Capture] Hotkey {HOTKEY_CAPTURE}")
        self.root.after(0, self._handle_capture_hotkey)

    def _on_api_hotkey_pressed(self) -> None:
        self.root.after(0, self._prompt_api_key_if_needed)

    def _effective_api_key(self) -> str:
        if self._session_api_key:
            return self._session_api_key.strip()
        return NVIDIA_API_KEY

    def _prompt_api_key_if_needed(self) -> None:
        key = self._effective_api_key()
        if _api_key_looks_valid(key):
            self._show_message("Cheie deja setată", show_copy=False)
            return
        self._prompt_api_key()

    def _prompt_api_key(self) -> None:
        if self._api_prompt_open:
            return
        self._api_prompt_open = True
        key = simpledialog.askstring(
            "NVIDIA API key",
            "Introdu cheia NVIDIA (nvapi-...).\nCheia este doar pentru sesiunea curentă.",
            parent=self.root,
        )
        try:
            if key is None:
                return
            key = key.strip()
            if not key:
                self._session_api_key = ""
                self._show_message("Cheie ștearsă", show_copy=False)
                return
            if not _api_key_looks_valid(key):
                self._show_message("Cheie invalidă", show_copy=False)
                return
            self._session_api_key = key
            self._show_message("Cheie setată", show_copy=False)
        finally:
            self._api_prompt_open = False

    def _handle_hotkey(self) -> None:
        if self._busy or self._region_select_active:
            return

        api_key = self._effective_api_key()
        if not api_key:
            self._show_message(f"Setează cheia ({HOTKEY_SET_API_KEY.upper()})", show_copy=False)
            return
        if not _api_key_looks_valid(api_key):
            self._show_message("Cheie API invalidă", show_copy=False)
            return

        clipboard_text, image_jpeg = _read_clipboard_payload()
        if not clipboard_text and not image_jpeg:
            self._show_message("Nimic copiat", show_copy=False)
            return

        if self._last_api_call > 0:
            elapsed = time.monotonic() - self._last_api_call
            if elapsed < API_MIN_INTERVAL_SEC:
                wait_sec = max(1, math.ceil(API_MIN_INTERVAL_SEC - elapsed))
                self._show_message(f"Așteaptă {wait_sec}s", show_copy=False)
                return

        self._last_clipboard = clipboard_text
        self._busy = True
        loading = "…+📷" if image_jpeg else "..."
        self._show_message(loading, show_copy=False)

        thread = threading.Thread(
            target=self._query_nvidia,
            args=(clipboard_text, image_jpeg, api_key),
            daemon=True,
        )
        thread.start()

    def _handle_capture_hotkey(self) -> None:
        if self._busy or self._region_select_active:
            return

        api_key = self._effective_api_key()
        if not api_key:
            self._show_message(f"Setează cheia ({HOTKEY_SET_API_KEY.upper()})", show_copy=False)
            return
        if not _api_key_looks_valid(api_key):
            self._show_message("Cheie API invalidă", show_copy=False)
            return

        if self._last_api_call > 0:
            elapsed = time.monotonic() - self._last_api_call
            if elapsed < API_MIN_INTERVAL_SEC:
                wait_sec = max(1, math.ceil(API_MIN_INTERVAL_SEC - elapsed))
                self._show_message(f"Așteaptă {wait_sec}s", show_copy=False)
                return

        self._start_region_select(api_key)

    def _start_region_select(self, api_key: str) -> None:
        """Deschide selector (chenar punctat), apoi trimite zona la API."""
        self._region_select_active = True

        def on_capture(image_jpeg: bytes | None) -> None:
            self._region_select_active = False
            if not image_jpeg:
                print("[Capture] Anulat sau zonă prea mică.")
                return
            print(f"[Capture] Zonă OK ({len(image_jpeg) // 1024} KB JPEG)")
            self._last_clipboard = ""
            self._busy = True
            self._show_message("…+📷", show_copy=False)
            thread = threading.Thread(
                target=self._query_nvidia,
                args=("", image_jpeg, api_key),
                daemon=True,
            )
            thread.start()

        try:
            RegionSelectOverlay(self.root, on_capture)
        except Exception as exc:
            self._region_select_active = False
            print(f"[Capture] Nu s-a putut deschide selectorul: {exc}")
            self._show_message("Captură eșuată", show_copy=False)

    def _query_nvidia(
        self,
        question_text: str,
        image_jpeg: bytes | None = None,
        api_key: str = "",
    ) -> None:
        try:
            if not api_key:
                self.root.after(0, lambda: self._finish_query("Fără cheie API", ""))
                return
            if not _api_key_looks_valid(api_key):
                self.root.after(0, lambda: self._finish_query("Cheie API invalidă", ""))
                return

            self._last_api_call = time.monotonic()

            client = _create_nvidia_client(api_key)

            def on_retry(attempt: int, wait_sec: float, model: str) -> None:
                label = f"Reîncerc {attempt}…"
                print(f"[NVIDIA] {label} {model}, pauză {wait_sec:.1f}s")
                self.root.after(0, lambda: self._show_message(label, show_copy=False))

            if image_jpeg:
                print(
                    f"[Clipboard] Imagine base64: "
                    f"{len(image_jpeg) // 1024} KB JPEG (max {IMAGE_MAX_DIMENSION_PX}px)"
                )

            model = _pick_nvidia_model(image_jpeg)
            t0 = time.monotonic()
            raw_answer = _generate_nvidia_with_retry(
                client,
                question_text,
                image_jpeg,
                status_callback=on_retry,
            )
            elapsed = time.monotonic() - t0
            print(
                f"[NVIDIA] {elapsed:.1f}s | {model} | "
                f"max_tokens={_max_output_tokens_for(question_text, image_jpeg)}"
            )
            if not raw_answer:
                self.root.after(0, lambda: self._finish_query("Fără răspuns", ""))
                return

            display, copy_text = self._parse_model_response(question_text, raw_answer)
            self.root.after(0, lambda d=display, c=copy_text: self._finish_query(d, c))
        except (APIStatusError, RateLimitError) as exc:
            display = _api_error_display(exc)
            print(f"[NVIDIA] {display}: {exc}")
            self.root.after(0, lambda d=display: self._finish_query(d, ""))
        except Exception as exc:
            display = _api_error_display(exc)
            print(f"[Quiz Solver] {display}: {exc}")
            self.root.after(0, lambda d=display: self._finish_query(d, ""))

    def _finish_query(self, display: str, copy_text: str) -> None:
        self._busy = False
        self._last_display = display
        self._last_copy_text = self._sanitize_copy_text(copy_text) if copy_text else ""
        has_copy = bool(copy_text) and display not in NO_COPY_DISPLAYS and not display.startswith(
            ("Prea rapid", "Eroare API (", "Reîncerc")
        )
        self._show_message(display, show_copy=has_copy)

    def _show_message(self, text: str, *, show_copy: bool) -> None:
        if self._fade_job:
            self.root.after_cancel(self._fade_job)
            self._fade_job = None

        self.root.attributes("-alpha", 1.0)
        self.status_label.config(text=self._truncate_display(text))

        if show_copy:
            self.copy_btn.pack(side=tk.LEFT)
        else:
            self.copy_btn.pack_forget()

        self._position_window()
        self.root.deiconify()
        self.root.lift()

    def _on_copy_clicked(self) -> None:
        if self._drag_moved:
            self._drag_moved = False
            return
        if self._last_copy_text:
            pyperclip.copy(self._last_copy_text)
        elif self._last_display:
            pyperclip.copy(self._last_display)

        self._fade_out_and_hide()

    def _fade_out_and_hide(self) -> None:
        self.copy_btn.pack_forget()
        self._fade_step(1.0)

    def _fade_step(self, alpha: float) -> None:
        if alpha <= 0.15:
            self.root.withdraw()
            self.root.attributes("-alpha", 1.0)
            self._fade_job = None
            return

        next_alpha = alpha - 0.18
        self.root.attributes("-alpha", max(next_alpha, 0.0))
        self._fade_job = self.root.after(35, lambda: self._fade_step(next_alpha))

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _sanitize_copy_text(text: str) -> str:
        """Un singur paragraf; fără liste, markdown sau derive umask inutile."""
        text = QuizSolverApp._strip_code_fences(text.strip())
        if re.search(r"(?i)\bNOT\s*\(\s*0666|De Morgan\b", text):
            text = re.sub(r"(?is)\bNOT\s*\(.*?(?=\n\n|\Z)", "", text).strip()
        if text.upper().startswith("R:"):
            text = text[2:].strip()
        if not text or "\n-" not in text and not re.search(r"(?m)^\s*[-•*]\s+", text):
            return text
        parts: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[-•*]\s+", "", line)
            line = re.sub(r"^\d+[\.\)]\s+", "", line)
            parts.append(line)
        if not parts:
            return text
        merged = " ".join(parts)
        merged = re.sub(r"\s+", " ", merged).strip()
        return merged

    @staticmethod
    def _truncate_display(text: str, max_len: int = DISPLAY_MAX_CHARS) -> str:
        text = text.strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        text = text.strip()
        if not text.startswith("```"):
            return text
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def _looks_like_code_question(text: str) -> bool:
        patterns = (
            r"(?i)\b(scrie|scrieți|write|implement|realizați|realizeaza)\b.*\b(program|script)\b",
            r"(?i)\bprogram\s+(c|c\+\+|java|python|shell)\b",
            r"(?i)\bshell\s+script\b",
            r"(?i)\b(fork|multiprocess|pipe|exec)\b",
            r"(?i)#include\s*<",
        )
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _copy_looks_like_code(text: str) -> bool:
        markers = ("#include", "int main", "def ", "#!/", "public class", "fn main", "<?php")
        return any(m in text for m in markers) or bool(re.search(r"(?m)^\s*#", text))

    @classmethod
    def _parse_model_response(cls, question_text: str, raw: str) -> tuple[str, str]:
        if not raw:
            return "?", ""

        structured = cls._parse_structured_response(raw)
        if structured:
            qtype, short, copy_text = structured
            if (
                qtype == "OPEN"
                and cls._looks_like_code_question(question_text)
                and copy_text
                and not cls._copy_looks_like_code(copy_text)
                and len(copy_text) < 200
            ):
                return "Cod lipsă?", ""
            return short or "?", copy_text or short or ""

        short, answer = cls._parse_answer(raw.splitlines()[0])
        copy_text = cls._resolve_copy_text(question_text, answer, raw)
        display = raw.splitlines()[0].strip() if raw else "?"
        if short and answer:
            display = f"{short}. {answer}" if short else answer
        return display or "?", copy_text

    @staticmethod
    def _looks_like_short_definition(text: str) -> bool:
        if QuizSolverApp._looks_like_mcq(text) or len(text) > 180:
            return False
        return bool(
            re.search(
                r"(?i)\b(ce este|ce e|ce sunt|defini|definiți|definiti|what is)\b",
                text,
            )
        )

    @staticmethod
    def _looks_like_open_explanation(text: str) -> bool:
        if QuizSolverApp._looks_like_mcq(text):
            return False
        if QuizSolverApp._looks_like_short_definition(text):
            return False
        patterns = (
            r"(?i)\b(argumentați|argumentati|explicați|explicati|descrieți|descrieti)\b",
            r"(?i)\b(care este|care vor fi|care va fi|de ce|cum|rezultatul)\b",
            r"(?i)\b(calculați|calculati|determinați|determinati|justificați)\b",
            r"(?i)\b(scrie|scrieți|implement|realizați|program)\b",
        )
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _is_garbage_structured_short(short: str, copy_text: str) -> bool:
        blob = f"{short} {copy_text}".lower()
        return any(
            token in blob
            for token in ("n/a", "not applicable", "expects explanation", "no single-choice")
        )

    @classmethod
    def _parse_structured_response(cls, raw: str) -> tuple[str, str, str] | None:
        lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip() and ln.strip() != "==="]
        if not lines:
            return None

        header_re = re.compile(
            r"^(MCQ|OPEN)\|\|\|(.+?)\|\|\|(.*)$",
            flags=re.IGNORECASE | re.DOTALL,
        )
        blocks: list[tuple[str, str, str, int]] = []
        for idx, line in enumerate(lines):
            line = line.strip().strip("`")
            match = header_re.match(line)
            if match:
                blocks.append(
                    (
                        match.group(1).upper(),
                        match.group(2).strip().strip('"').strip("'"),
                        match.group(3).strip().strip('"').strip("'"),
                        idx,
                    )
                )

        if not blocks:
            return None

        def body_after(start_idx: int) -> str:
            end = len(lines)
            for _, _, _, idx in blocks:
                if idx > start_idx:
                    end = idx
                    break
            extra = lines[start_idx + 1 : end]
            return "\n".join(extra).strip()

        open_blocks = [b for b in blocks if b[0] == "OPEN"]
        mcq_blocks = [b for b in blocks if b[0] == "MCQ"]

        for qtype, short, inline_copy, idx in open_blocks + mcq_blocks:
            if qtype == "MCQ" and cls._is_garbage_structured_short(short, inline_copy):
                continue
            if qtype == "OPEN":
                extra = body_after(idx)
                copy_text = inline_copy or extra
                if inline_copy and extra:
                    copy_text = f"{inline_copy}\n{extra}".strip()
                copy_text = cls._strip_code_fences(copy_text)
            else:
                copy_text = cls._strip_code_fences(inline_copy)
            if copy_text in {"", "...", "…"}:
                copy_text = ""
            return qtype, short, copy_text

        return None

    @staticmethod
    def _parse_answer(display: str) -> tuple[str | None, str | None]:
        cleaned = display.strip().strip('"').strip("'")
        match = re.match(
            r"^(?:(\d+)\.\s*)?(.+)$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            return None, cleaned or None

        number, answer = match.group(1), match.group(2).strip()
        if re.fullmatch(r"(?i)true|false", answer):
            return number, answer.capitalize()
        letter_match = re.match(r"^([A-Ea-e])\b", answer)
        if letter_match:
            return number, letter_match.group(1).upper()
        return number, answer

    @classmethod
    def _resolve_copy_text(
        cls,
        question_text: str,
        answer: str | None,
        raw: str,
    ) -> str:
        if not answer:
            return raw.strip()

        if answer in {"True", "False"}:
            return answer

        if len(answer) == 1 and answer.isalpha() and cls._looks_like_mcq(question_text):
            return answer.upper()

        if cls._looks_like_mcq(question_text) and len(answer) <= 3:
            letter_match = re.match(r"^([A-E])$", answer, re.IGNORECASE)
            if letter_match:
                return letter_match.group(1).upper()

        return answer if len(raw.splitlines()) == 1 else raw.strip()

    def _load_saved_position(self) -> tuple[int, int] | None:
        try:
            with open(WINDOW_POS_FILE, encoding="utf-8") as fh:
                payload = json.load(fh)
            x = int(payload.get("x"))
            y = int(payload.get("y"))
            return (x, y)
        except Exception:
            return None

    def _save_manual_position(self) -> None:
        if self._manual_position is None:
            return
        x, y = self._manual_position
        try:
            with open(WINDOW_POS_FILE, "w", encoding="utf-8") as fh:
                json.dump({"x": x, "y": y}, fh)
        except Exception:
            pass

    @staticmethod
    def _looks_like_mcq(question_text: str) -> bool:
        patterns = (
            r"(?im)^\s*[A-E][\.\)\:\-]\s+\S",
            r"(?im)^\s*\(\s*[A-E]\s*\)\s+\S",
            r"(?im)\bTrue\s*/\s*False\b",
            r"(?im)\b(Adevărat|Fals)\b",
        )
        return any(re.search(pattern, question_text) for pattern in patterns)

    @staticmethod
    def _extract_option_by_letter(question_text: str, letter: str) -> str | None:
        letter = letter.upper()
        patterns = (
            rf"(?im)^\s*{letter}[\.\)\:\-]\s*(.+?)(?=^\s*[A-E][\.\)\:\\-]|\Z)",
            rf"(?is)\(\s*{letter}\s*\)\s*(.+?)(?=\(\s*[A-E]\s*\)|\Z)",
            rf"(?is)\b{letter}\)\s*(.+?)(?=\b[A-E]\)|\Z)",
        )
        for pattern in patterns:
            match = re.search(pattern, question_text)
            if match:
                return re.sub(r"\s+", " ", match.group(1)).strip()
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _install_ctrl_c_handler(self) -> None:
        """Ctrl+C în terminal: Tkinter nu primește SIGINT în mainloop fără polling."""

        def on_sigint(_signum: int, _frame: object | None) -> None:
            if self._shutting_down:
                print("\nOprire forțată.")
                self._force_exit()
                return
            print("\nOprire…")
            self._shutdown_requested = True
            try:
                self.root.after(0, self.shutdown)
            except tk.TclError:
                self._force_exit()

        signal.signal(signal.SIGINT, on_sigint)

        def poll_shutdown() -> None:
            if self._shutdown_requested and not self._shutting_down:
                self.shutdown()
                return
            try:
                if self.root.winfo_exists():
                    self.root.after(200, poll_shutdown)
            except tk.TclError:
                pass

        self.root.after(200, poll_shutdown)

    @staticmethod
    def _release_keyboard_hooks() -> None:
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    @staticmethod
    def _force_exit() -> None:
        QuizSolverApp._release_keyboard_hooks()
        os._exit(0)

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._busy = False
        # Cheia introdusă prin hotkey rămâne doar în sesiunea curentă.
        self._session_api_key = ""

        if self._fade_job:
            try:
                self.root.after_cancel(self._fade_job)
            except Exception:
                pass
            self._fade_job = None

        self._release_keyboard_hooks()

        try:
            self.root.withdraw()
        except tk.TclError:
            pass
        try:
            self.root.quit()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _exit_app(self) -> None:
        self.shutdown()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    cli_api_key = ""
    if len(sys.argv) > 1:
        candidate = (sys.argv[1] or "").strip()
        if _api_key_looks_valid(candidate):
            cli_api_key = candidate
        else:
            print("Avertisment: argumentul primit nu este o cheie NVIDIA validă (nvapi-...).")

    if not NVIDIA_API_KEY:
        print(
            "Avertisment: cheia NVIDIA lipsește în setări. "
            f"Poți seta temporar cheia din aplicație cu {HOTKEY_SET_API_KEY.upper()}."
        )
    elif hint := _api_key_format_hint(NVIDIA_API_KEY):
        print(f"Avertisment: {hint}")
        print(f"Poți introduce cheia corectă temporar cu {HOTKEY_SET_API_KEY.upper()}.")
    else:
        print("Cheie API NVIDIA (nvapi-) — OK.")
        print(
            f"Quiz Solver activ. Clipboard → {HOTKEY.upper()}. "
            f"Captură zonă → {HOTKEY_CAPTURE.upper()}. "
            f"Setează cheie sesiune: {HOTKEY_SET_API_KEY.upper()}. "
            f"Pauză min. {API_MIN_INTERVAL_SEC:.0f}s. "
            f"Text rapid: {NVIDIA_MODEL_FAST} | Imagine: {NVIDIA_MODEL_VLM}. "
            "Ieșire: click dreapta → Exit sau Ctrl+C."
        )
        if HOTKEY in {"f10", "f11", "f12", "f9"}:
            print(
                f"Atenție: '{HOTKEY}' singur e adesea blocat de Windows/browser. "
                "Folosește o combinație cu Ctrl/Shift în application_settings.json."
            )
    app: QuizSolverApp | None = None
    try:
        app = QuizSolverApp(initial_api_key=cli_api_key)
        app.run()
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("\nOprire…")
    finally:
        if app is not None:
            app.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    main()
