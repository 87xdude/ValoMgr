# -*- coding: utf-8 -*-
"""
Start der App mit robustem Windows-Taskleisten-Icon:
- Persistenter Vault-Pfad (auch für PyInstaller OneFile).
- High-DPI/Scaling Setup vor QApplication.
- Windows Taskbar Icon: AppUserModelID + WM_SETICON + SetClassLongPtrW (small/big/class icon) auf allen Top-Level-Fenstern.
- Lädt Settings/Vault, öffnet MainWindow und triggert startup_unlock().
"""

from __future__ import annotations
import os
import sys
import ctypes
from ctypes import wintypes
import traceback

# ------------------ Persistenter Vault-Pfad (OneFile-sicher) ------------------

def _is_temp_path(p: str) -> bool:
    if not p:
        return True
    p = os.path.abspath(p)
    tmp_candidates = {
        os.getenv("TEMP"),
        os.getenv("TMP"),
        os.path.join(os.getenv("LOCALAPPDATA") or "", "Temp"),
    }
    tmp_candidates = {os.path.abspath(x) for x in tmp_candidates if x}
    if any(p.lower().startswith(x.lower()) for x in tmp_candidates):
        return True
    # PyInstaller-Extraktionsordner
    if hasattr(sys, "_MEIPASS") and os.path.abspath(getattr(sys, "_MEIPASS")) in p:  # type: ignore[attr-defined]
        return True
    return False

def _is_writable_dir(d: str) -> bool:
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False

def _exe_dir() -> str:
    # Ordner der EXE (frozen) bzw. Projektroot (dev)
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _user_data_dir() -> str:
    app = os.getenv("APPDATA")
    if app:
        return os.path.join(app, "CValoMgr")
    return os.path.join(os.path.expanduser("~"), "CValoMgr")

def resolve_persistent_vault_path(settings) -> str:
    """
    Stabiler Speicherort für vault.dat:
      1) settings.vault_path (wenn gültig)
      2) ENV CVALOMGR_VAULT
      3) neben der EXE (portable)
      4) aktuelles Arbeitsverzeichnis
      5) %APPDATA%\CValoMgr\vault.dat
    """
    cur = getattr(settings, "vault_path", None) or getattr(settings, "vaultPath", None)
    if cur and not _is_temp_path(cur) and _is_writable_dir(os.path.dirname(cur)):
        return os.path.abspath(cur)

    env_vault = os.getenv("CVALOMGR_VAULT")
    if env_vault and not _is_temp_path(env_vault) and _is_writable_dir(os.path.dirname(env_vault)):
        return os.path.abspath(env_vault)

    exe_vault = os.path.join(_exe_dir(), "vault.dat")
    if os.path.isfile(exe_vault) or _is_writable_dir(os.path.dirname(exe_vault)):
        return os.path.abspath(exe_vault)

    cwd_vault = os.path.join(os.getcwd(), "vault.dat")
    if os.path.isfile(cwd_vault) or _is_writable_dir(os.path.dirname(cwd_vault)):
        return os.path.abspath(cwd_vault)

    appdata_vault = os.path.join(_user_data_dir(), "vault.dat")
    _is_writable_dir(os.path.dirname(appdata_vault))  # sicherstellen
    return os.path.abspath(appdata_vault)

# ------------------ High-DPI Setup (vor QApplication!) ------------------

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtWidgets import QApplication, QMessageBox

try:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
except Exception:
    pass

QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# ------------------ Windows: AppID & Taskleisten-Icon erzwingen ------------------

def _set_windows_appusermodel_id(app_id: str):
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

def _apply_windows_icons(hwnd: int, ico_path: str):
    """
    Setzt Small/Big sowie Klassen-Icon für ein HWND (WM_SETICON + SetClassLongPtrW).
    """
    if os.name != "nt" or not os.path.exists(ico_path) or not hwnd:
        return
    try:
        user32 = ctypes.windll.user32
        WM_SETICON = 0x0080
        ICON_SMALL, ICON_BIG = 0, 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        GCLP_HICON, GCLP_HICONSM = -14, -34

        LoadImageW = user32.LoadImageW
        LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                               wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        LoadImageW.restype = wintypes.HANDLE

        SendMessageW = user32.SendMessageW
        SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        SendMessageW.restype = wintypes.LRESULT

        if ctypes.sizeof(ctypes.c_void_p) == 8:
            SetClassLongPtrW = user32.SetClassLongPtrW
            SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HANDLE]
            SetClassLongPtrW.restype = wintypes.ULONG_PTR
        else:
            SetClassLongPtrW = user32.SetClassLongW
            SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
            SetClassLongPtrW.restype = wintypes.ULONG

        def _load(sz: int):
            return LoadImageW(None, ico_path, IMAGE_ICON, sz, sz, LR_LOADFROMFILE)

        h16  = _load(16)
        h24  = _load(24)
        h32  = _load(32)
        h48  = _load(48)
        h256 = _load(256)

        if h16:
            SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h16)
            SetClassLongPtrW(hwnd, GCLP_HICONSM, h16)
        for h in (h256, h48, h32, h24):
            if h:
                SendMessageW(hwnd, WM_SETICON, ICON_BIG, h)
                SetClassLongPtrW(hwnd, GCLP_HICON, h)
                break
    except Exception:
        pass

def _apply_icon_to_all_windows(ico_path: str, app: QApplication):
    """
    Iteriert alle Top-Level-Fenster (sichtbar & verborgen) und setzt Icons.
    Mehrfach aufrufen (Timing/Styles).
    """
    if os.name != "nt" or not ico_path:
        return
    try:
        tops = list(app.topLevelWidgets()) + list(app.topLevelWindows())
        seen: set[int] = set()
        for w in tops:
            try:
                hwnd = int(w.winId())
            except Exception:
                continue
            if hwnd and hwnd not in seen:
                _apply_windows_icons(hwnd, ico_path)
                seen.add(hwnd)
    except Exception:
        pass

# ------------------ Eigene Module (absolute Importe) ------------------

from app.ui.main_window import MainWindow
from app.core.vault import Vault
from app.core.settings import Settings
from app.core.models import AppState

# ------------------ Settings Loader ------------------

def _safe_settings_load() -> Settings:
    try:
        if hasattr(Settings, "load") and callable(getattr(Settings, "load")):
            return Settings.load()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        return Settings()
    except Exception:
        class _S: pass
        s = _S()
        s.riot_api_key = ""
        s.henrikdev_api_key = ""
        s.henrik_base_url = "https://api.henrikdev.xyz"
        s.riot_client_path = ""
        s.vault_path = ""
        s.auto_type_hotkey = "<CTRL><ALT>a"
        return s  # type: ignore[return-value]

def _settings_save_if_possible(settings: Settings) -> None:
    try:
        if hasattr(settings, "save") and callable(getattr(settings, "save")):
            settings.save()  # type: ignore[attr-defined]
    except Exception:
        pass

# ------------------ App-Start ------------------

def run():
    # Eigene AppID (per EXE-Name) für saubere Taskleisten-Gruppierung/Pinning
    exe_name = os.path.splitext(os.path.basename(sys.executable if getattr(sys, "frozen", False) else "dev"))[0]
    app_id = os.environ.get("CVALOMGR_APPID") or f"AccountMgr.{exe_name}"
    _set_windows_appusermodel_id(app_id)

    app = QApplication(sys.argv)
    app.setApplicationName("AccountMgr")
    app.setOrganizationName("AccountMgr")
    app.setApplicationDisplayName("AccountMgr")

    # App-Icon (OneDir & Dev kompatibel)
    res_dir = os.path.join(_exe_dir(), "app", "resources")
    ico_candidates = ["exe_logo.ico", "sidebar_logo.ico"]
    ico_path = next((os.path.join(res_dir, fn) for fn in ico_candidates
                     if os.path.exists(os.path.join(res_dir, fn))), None)
    if ico_path:
        # QIcon mit expliziten Größen füllen (hilft Qt-seitig)
        icon = QIcon()
        for sz in (16, 20, 24, 32, 40, 48, 64, 128, 256):
            icon.addFile(ico_path, QSize(sz, sz))
        app.setWindowIcon(icon)

    # Settings laden & Vault-Pfad stabilisieren
    settings = _safe_settings_load()
    vault_path = resolve_persistent_vault_path(settings)
    try:
        setattr(settings, "vault_path", vault_path)
        _settings_save_if_possible(settings)
    except Exception:
        pass

    # Vault & State
    try:
        vault = Vault(vault_path)
    except Exception as e:
        QMessageBox.critical(None, "Startfehler", f"Konnte Vault initialisieren:\n{e}")
        raise

    state = AppState()

    # Hauptfenster
    win = MainWindow(vault, settings, state)

    # Fenster-Icon (zusätzlich zu app.setWindowIcon)
    if ico_path:
        try:
            win.setWindowIcon(QIcon(ico_path))
        except Exception:
            pass

    # Beim Start entsperren
    try:
        win.startup_unlock()
    except Exception:
        traceback.print_exc()

    win.show()

    # --- Icons auf ALLE Top-Level-Fenster forcieren (Timing-Varianten) ---
    if ico_path:
        QTimer.singleShot(0,    lambda: _apply_icon_to_all_windows(ico_path, app))
        QTimer.singleShot(200,  lambda: _apply_icon_to_all_windows(ico_path, app))
        QTimer.singleShot(1000, lambda: _apply_icon_to_all_windows(ico_path, app))

    sys.exit(app.exec())

if __name__ == "__main__":
    run()
