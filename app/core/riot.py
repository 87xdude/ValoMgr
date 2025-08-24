from __future__ import annotations
import os
import subprocess
import time
import ctypes
from typing import Optional, Callable

# ---------- Win32 Helpers ----------
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

# VK-Codes
_VK_TAB   = 0x09
_VK_SHIFT = 0x10

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("hwndActive", ctypes.c_void_p),
        ("hwndFocus", ctypes.c_void_p),
        ("hwndCapture", ctypes.c_void_p),
        ("hwndMenuOwner", ctypes.c_void_p),
        ("hwndMoveSize", ctypes.c_void_p),
        ("hwndCaret", ctypes.c_void_p),
        ("rcCaret", ctypes.c_long * 4),
    ]

def _enum_windows():
    result = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _cb(hwnd, lParam):
        if _user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            result.append(hwnd)
        return True
    _user32.EnumWindows(_cb, 0)
    return result

def _win_get_title(hwnd) -> str:
    length = _user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, length + 1)
    return buf.value

def _win_get_class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 256)
    return buf.value

def _get_riot_window_hwnd() -> Optional[int]:
    for hwnd in _enum_windows():
        title = _win_get_title(hwnd).lower()
        # Häufig "Riot Client"
        if "riot client" in title:
            return hwnd
    return None

def _bring_to_front(hwnd) -> bool:
    if not hwnd:
        return False
    SW_RESTORE = 9
    _user32.ShowWindow(ctypes.c_void_p(hwnd), SW_RESTORE)
    _user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    return True

def _thread_id(hwnd):
    return _user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), None)

def _get_focus_hwnd_of_thread(thread_id):
    gti = GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(GUITHREADINFO)
    if _user32.GetGUIThreadInfo(thread_id, ctypes.byref(gti)):
        return gti.hwndFocus
    return None

# Tastatur-Input
PUL = ctypes.POINTER(ctypes.c_ulong)
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ki", KEYBDINPUT)]

def _press_vk(vk, down=True):
    ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0 if down else 2, time=0, dwExtraInfo=None)
    inp = INPUT(type=1, ki=ki)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def _send_shift_tab(times=1, delay=0.05):
    for _ in range(max(1, times)):
        _press_vk(_VK_SHIFT, True)
        _press_vk(_VK_TAB, True);  time.sleep(delay)
        _press_vk(_VK_TAB, False); time.sleep(delay/2)
        _press_vk(_VK_SHIFT, False); time.sleep(delay)

# ---------- Öffnen/ Fokus Riot Client ----------
def start_riot(riot_client_path: Optional[str], game: Optional[str] = None, log: Optional[Callable[[str], None]] = None):
    """
    Startet den Riot Client (nicht das Spiel). Existiert bereits ein Fenster, wird nur fokussiert.
    """
    def _log(msg):
        if log:
            try: log(msg)
            except Exception: pass

    hwnd = _get_riot_window_hwnd()
    if hwnd:
        _log("Riot-Client läuft bereits – Fenster fokussieren.")
        _bring_to_front(hwnd)
        return

    if not riot_client_path or not os.path.isfile(riot_client_path):
        _log("Riot-Client Pfad fehlt/ungültig – versuche Standardstart (nur Fokus).")
        return  # Wir versuchen später nur Fokus

    try:
        # Ohne Spiel-Launch-Argumente starten
        subprocess.Popen([riot_client_path], close_fds=True)
        _log("Riot-Client gestartet.")
        # kurze Wartezeit bis Fenster da ist
        for _ in range(40):
            time.sleep(0.1)
            hwnd = _get_riot_window_hwnd()
            if hwnd:
                break
        if hwnd:
            _bring_to_front(hwnd)
    except Exception as e:
        _log(f"Riot-Client Start fehlgeschlagen: {e}")

def focus_riot_login_window(log: Optional[Callable[[str], None]] = None) -> bool:
    hwnd = _get_riot_window_hwnd()
    if not hwnd:
        if log: log("Riot-Login: Fenster nicht gefunden.")
        return False
    ok = _bring_to_front(hwnd)
    if log: log("Riot-Login: Fenster fokussiert." if ok else "Riot-Login: Fokus fehlgeschlagen.")
    return ok

def ensure_login_only(duration: float = 8.0, kill: bool = True, log: Optional[Callable[[str], None]] = None):
    """
    Lässt dem Login etwas Zeit und verhindert ggf. Spielstart (optional).
    """
    def _log(msg):
        if log:
            try: log(msg)
            except Exception: pass

    time.sleep(max(0.0, duration))
    if not kill:
        return
    # Optional: bekannte Spielprozesse terminieren, falls doch gestartet (best effort)
    try:
        for proc in ("VALORANT-Win64-Shipping.exe", "League of Legends.exe"):
            subprocess.run(["taskkill", "/IM", proc, "/T", "/F"], capture_output=True, text=True)
        _log("Login-Only: ggf. gestartete Spielprozesse beendet.")
    except Exception:
        pass

# ---------- Fokus Username-Feld ----------
def focus_username_field(log: Optional[Callable[[str], None]] = None,
                         tab_back_steps: int = 6, verify: bool = True,
                         sleep_between: float = 0.08) -> bool:
    """
    Versucht, im Riot-Client das Benutzername-Feld zu fokussieren.
    1) UIAutomation (uiautomation / pywinauto), falls installiert
    2) Fallback: SHIFT+TAB zum ersten Edit-Feld
    """
    def _log(msg):
        if log:
            try: log(msg)
            except Exception: pass

    hwnd = _get_riot_window_hwnd()
    if not hwnd:
        _log("Riot-Login: Fenster nicht gefunden.")
        return False

    _bring_to_front(hwnd)
    time.sleep(sleep_between)

    # Pfad A: uiautomation
    try:
        try:
            import uiautomation as uia
            win = uia.WindowControl(searchDepth=1, NameRegex=".*Riot Client.*")
            edit = None
            for e in win.GetChildren():
                if isinstance(e, uia.EditControl) and e.IsEnabled and e.IsOffscreen is False:
                    edit = e; break
            if edit:
                edit.SetFocus(); time.sleep(sleep_between)
                _log("Riot-Login: Fokus via UIAutomation auf erstes Edit gesetzt.")
                return True
        except Exception:
            pass

        # Pfad A2: pywinauto (UIA)
        try:
            from pywinauto import Desktop
            d = Desktop(backend='uia')
            win = d.window(title_re=".*Riot Client.*")
            edits = win.descendants(control_type="Edit")
            for e in edits:
                try:
                    if e.is_visible() and e.is_enabled():
                        e.set_focus(); time.sleep(sleep_between)
                        _log("Riot-Login: Fokus via pywinauto auf erstes Edit gesetzt.")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
    except Exception:
        pass

    # Pfad B: Fallback ohne Abhängigkeiten
    tid = _thread_id(hwnd)
    before = _get_focus_hwnd_of_thread(tid)
    _send_shift_tab(max(1, tab_back_steps), delay=0.06)
    time.sleep(sleep_between)

    if not verify:
        _log("Riot-Login: Fallback-Fokus ohne Verifikation durchgeführt.")
        return True

    after = _get_focus_hwnd_of_thread(tid)
    cls = _win_get_class_name(after) if after else ""
    plausible = ("Edit", "Chrome_WidgetWin_", "Chrome_RenderWidgetHostHWND")
    ok = bool(after) and any(cls.startswith(p) for p in plausible)

    _log(f"Riot-Login: Fallback-Fokus → hwnd=0x{int(after or 0):X}, class='{cls}', ok={ok}")
    return ok
