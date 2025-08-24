
from __future__ import annotations
import time, platform
from typing import Optional

# We try pyautogui first (cross-platform), then keyboard as fallback.
try:
    import pyautogui as _py
    _HAS_PYAUTO = True
except Exception:
    _py = None
    _HAS_PYAUTO = False

try:
    import keyboard as _kb  # Windows-friendly
    _HAS_KB = True
except Exception:
    _kb = None
    _HAS_KB = False

class KeePassAutoTypeError(RuntimeError):
    pass

def _parse_hotkey(hk: str):
    """Return list of lower-case keys, e.g. 'Ctrl+Alt+A' -> ['ctrl','alt','a']"""
    keys = [k.strip().lower() for k in (hk or "").replace("+", " ").split() if k.strip()]
    if not keys:
        raise KeePassAutoTypeError("Auto-Type Hotkey ist leer. Bitte in den Einstellungen setzen (z. B. Ctrl+Alt+A).")
    return keys

def trigger_autotype(hotkey: str, *, pre_delay: float = 0.15):
    """Trigger KeePassXC global Auto-Type hotkey only."""
    keys = _parse_hotkey(hotkey)
    time.sleep(pre_delay)
    if _HAS_PYAUTO:
        _py.hotkey(*keys)
    elif _HAS_KB:
        for k in keys[:-1]:
            _kb.key_down(k)
        _kb.press_and_release(keys[-1])
        for k in keys[:-1][::-1]:
            _kb.key_up(k)
    else:
        raise KeePassAutoTypeError("Weder 'pyautogui' noch 'keyboard' verfügbar. Installiere z. B. 'pip install pyautogui'.")

def autotype_entry(hotkey: str, entry_hint: str, *, selection_delay: float = 0.35, type_interval: float = 0.02):
    """
    Trigger global Auto-Type und wählt gezielt einen Eintrag in der KeePassXC-Auswahlliste,
    indem der Eintragsname getippt und mit Enter bestätigt wird.

    Voraussetzungen in KeePassXC:
      Einstellungen → Auto-Type → 'Vor Auto-Type immer nachfragen' aktivieren
      (damit erscheint die Auswahl, in der getippt werden kann)

    Falls die Auswahl nicht erscheint (nur 1 Match), wird direkt Auto-Type ausgeführt.
    """
    if not entry_hint:
        return trigger_autotype(hotkey)

    # 1) Hotkey auslösen
    trigger_autotype(hotkey)

    # 2) kurz warten, bis KeePassXC-Auswahlliste im Fokus ist
    time.sleep(selection_delay)

    # 3) Eintragsnamen tippen + Enter
    if _HAS_PYAUTO:
        _py.typewrite(entry_hint, interval=type_interval)
        _py.press('enter')
    elif _HAS_KB:
        _kb.write(entry_hint, delay=type_interval)
        _kb.press_and_release('enter')
    else:
        raise KeePassAutoTypeError("Weder 'pyautogui' noch 'keyboard' verfügbar. Installiere z. B. 'pip install pyautogui'.")
