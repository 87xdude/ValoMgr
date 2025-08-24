from __future__ import annotations
import os, shutil, traceback, logging, logging.handlers
from datetime import datetime
from typing import Optional, Dict, List
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPalette, QImage, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QProgressDialog, QDialog,
    QHeaderView, QSizePolicy, QLabel, QFrame, QTabWidget, QToolButton, QStyle,
    QStackedLayout, QLineEdit, QPushButton, QInputDialog
)
from PySide6.QtCore import Qt, QSize

from ..core.models import Account, AppState, Game, Queue
from ..core.settings import Settings
from ..core.vault import Vault
from ..core.icons import get_rank_icon
from ..core.riot import start_riot, focus_riot_login_window, ensure_login_only, focus_username_field
from ..core.kpxc import trigger_autotype, autotype_entry
from ..core.ranks import fetch_valorant_rank, fetch_lol_tft_rank
from .add_edit_dialog import AddEditDialog
from .settings_dialog import SettingsDialog
from .log_dialog import LogDialog

USER_ROLE_KEY = Qt.UserRole + 1
ICON_SIZE = 28
ROW_HEIGHT = 32
LEFT_ICON_PX = 20
FORCE_WHITE_TINT = False


def _row_key(acc: Account) -> str:
    return f"{acc.game.value}|{acc.alias}|{acc.riot_id}"


def _tint_pixmap_white(pm: QPixmap) -> QPixmap:
    if pm.isNull():
        return pm
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    out = QPixmap(pm.size()); out.fill(Qt.transparent)
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode_Source)
    p.drawImage(0, 0, img)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QColor(255,255,255))
    p.end()
    return out


def _menu_icons_dir() -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, "resources", "menu_icons")


def _load_menu_icon(name: str) -> QIcon:
    path_base = os.path.join(_menu_icons_dir(), name + ".png")
    ico = QIcon()
    if os.path.exists(path_base):
        pm = QPixmap(path_base)
        if not pm.isNull():
            if FORCE_WHITE_TINT:
                pm = _tint_pixmap_white(pm)
            ico.addPixmap(pm)
        path_2x = os.path.join(_menu_icons_dir(), name + "@2x.png")
        if os.path.exists(path_2x):
            pm2 = QPixmap(path_2x)
            if not pm2.isNull():
                if FORCE_WHITE_TINT:
                    pm2 = _tint_pixmap_white(pm2)
                ico.addPixmap(pm2)
        if not ico.isNull():
            return ico
    # Fallback
    style_map = {
        "add": QStyle.SP_FileDialogNewFolder,
        "edit": QStyle.SP_FileDialogDetailedView,
        "delete": QStyle.SP_TrashIcon,
        "refresh": QStyle.SP_BrowserReload,
        "refresh_all": QStyle.SP_BrowserReload,
        "login": QStyle.SP_DialogYesButton,
        "export": QStyle.SP_DialogSaveButton,
        "import": QStyle.SP_DialogOpenButton,
        "settings": QStyle.SP_FileDialogInfoView,
        "log": QStyle.SP_MessageBoxInformation,
        "lock": QStyle.SP_DialogCloseButton,
    }
    sp = style_map.get(name, QStyle.SP_FileIcon)
    base = QMainWindow().style().standardIcon(sp)
    pm = base.pixmap(QSize(LEFT_ICON_PX, LEFT_ICON_PX))
    pm = _tint_pixmap_white(pm)
    ico.addPixmap(pm)
    return ico


# ---------- Valorant-Icon-Helper (Tracker-ähnliches Pack) ----------
def _normalize_valo_tier(tier: str) -> str:
    if tier is None:
        return ""
    t = str(tier).strip().lower().replace("-", " ").replace("_", " ")
    # DE → EN
    t = (t.replace("silber", "silver")
           .replace("gold", "gold")
           .replace("platin", "platinum")
           .replace("diamant", "diamond")
           .replace("strahlend", "radiant"))
    t = " ".join(t.split())
    # Tippfehler
    t = (t.replace("platum", "platinum")
           .replace("plati", "platinum")
           .replace("immotal", "immortal")
           .replace("ascandant", "ascendant"))
    # Kürzungen
    t = (t.replace("ascendant", "asc")
           .replace("platinum", "plat")
           .replace("diamond", "dia")
           .replace("immortal", "imm")
           .replace("radiant", "rad"))
    # Römisch → arabisch
    if t.endswith(" iii"): t = t[:-4] + "3"
    elif t.endswith(" ii"): t = t[:-3] + "2"
    elif t.endswith(" i"): t = t[:-2] + "1"
    return t.replace(" ", "")

def _valo_icons_folder(base_dir: str) -> str:
    return os.path.join(base_dir, "resources", "valo_tracker_icons")

def _search_fuzzy_icon(folder: str, key_noext: str) -> Optional[str]:
    for ext in (".png",".webp",".svg"):
        p = os.path.join(folder, key_noext + ext)
        if os.path.exists(p):
            return p
        low = key_noext.lower()
        try:
            for fn in os.listdir(folder):
                if low in fn.lower():
                    return os.path.join(folder, fn)
        except Exception:
            pass
    return None

def _valorant_icon_path_for_tier(base_dir: str, tier: str) -> Optional[str]:
    key = _normalize_valo_tier(tier)
    folder = _valo_icons_folder(base_dir)
    if not key:
        return None
    # 1) direkt
    p = _search_fuzzy_icon(folder, key)
    if p:
        return p
    # 2) Fallbacks
    num = key[-1] if key and key[-1] in "123" else ""
    base = key[:-1] if num else key
    if base.startswith(("platu", "plati")):
        base = "plat"
    candidates = []
    if num:
        if base.startswith("plat"):     candidates += [f"platinum{num}", f"plat{num}"]
        if base.startswith("dia"):      candidates += [f"diamond{num}", f"dia{num}"]
        if base.startswith("asc"):      candidates += [f"ascendant{num}", f"asc{num}"]
        if base.startswith("imm"):      candidates += [f"immortal{num}", f"imm{num}"]
    else:
        if base in ("rad", "radiant"):  candidates += ["radiant", "rad"]
        map_full = {"plat":"platinum", "dia":"diamond", "asc":"ascendant", "imm":"immortal"}
        if base in map_full: candidates.append(map_full[base])
    for cand in candidates:
        p = _search_fuzzy_icon(folder, cand)
        if p:
            return p
    return None


class MainWindow(QMainWindow):
    def __init__(self, vault: Vault, settings: Settings, state: AppState):
        super().__init__()
        self._init_logging()  # Datei-Logging + globale Exception-Hooks
        self.vault=vault; self.settings=settings; self.state=state; self.log=LogDialog(self)
        self.is_locked = False

        self.setWindowTitle("Riot Account Manager")
        self.resize(1280,760)

        central = QWidget(); self.setCentralWidget(central)
        self.stack = QStackedLayout(central)

        self.page_main = self._build_main_page()
        self.page_locked = self._build_locked_page()

        self.stack.addWidget(self.page_main)
        self.stack.addWidget(self.page_locked)
        self._show_locked_page(False)

        if self._vault_is_open():
            self._load_from_vault()

        self.reload_tables()

    # ==== Logging: Datei + UI ====
    def _init_logging(self):
        """Richtet File-Logging (Rotating) + globale Exception-Hooks ein."""
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            log_dir  = os.path.join(base_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "app.log")

            self._py_logger = logging.getLogger("CValoMgr")
            self._py_logger.setLevel(logging.INFO)
            if not self._py_logger.handlers:
                fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
                fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
                self._py_logger.addHandler(fh)

            # Ungefangene Exceptions → Log
            import sys, traceback as _tb
            def _hook(exc_type, exc, tb):
                msg = "".join(_tb.format_exception(exc_type, exc, tb))
                try:
                    self.log_error("Ungefangene Ausnahme", exc, extra=msg)
                except Exception:
                    self._py_logger.error("Ungefangene Ausnahme:\n%s", msg)
            sys.excepthook = _hook

            # Qt-Meldungen → Log (optional)
            try:
                from PySide6.QtCore import qInstallMessageHandler, QtMsgType
                def _qt_handler(mode, ctx, msg):
                    lvl = {QtMsgType.QtInfoMsg:"INFO", QtMsgType.QtWarningMsg:"WARNING",
                           QtMsgType.QtCriticalMsg:"ERROR", QtMsgType.QtFatalMsg:"CRITICAL"}.get(mode, "INFO")
                    try: self._py_logger.log(getattr(logging, lvl, logging.INFO), f"Qt: {msg}")
                    except Exception: pass
                qInstallMessageHandler(_qt_handler)
            except Exception:
                pass

            self._py_logger.info("=== CValoMgr gestartet ===")
        except Exception:
            pass

    def log_msg(self, msg: str, level: str = "INFO"):
        """Schreibt eine Nachricht mit Zeitstempel in UI-Log + Datei-Log."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        try:
            self.log.append(line)  # UI
        except Exception:
            pass
        try:
            lvl = getattr(logging, level.upper(), logging.INFO)
            if hasattr(self, "_py_logger"):
                self._py_logger.log(lvl, msg)  # Datei
        except Exception:
            pass

    def log_error(self, context: str, exc: Exception | None = None, extra: str | None = None):
        """Fehler-Logger mit Kontext + Exception + optionalem Stacktrace."""
        import traceback as _tb
        parts = [f"{context}"]
        if exc is not None:
            parts.append(f"{type(exc).__name__}: {exc}")
        try:
            tb = extra or _tb.format_exc()
            if tb and tb.strip() != "NoneType: None":
                parts.append(tb)
        except Exception:
            pass
        self.log_msg("\n".join(parts), level="ERROR")

    # -------- Start-Entsperrung (von main.py aufgerufen) --------
    def startup_unlock(self) -> bool:
        ok = False
        try:
            ok = bool(self._ensure_vault_open())
        except Exception:
            ok = False

        if ok:
            try:
                self._load_from_vault()
            except Exception as e:
                self.log_error("Startup: Laden aus Vault fehlgeschlagen", e)
            self._show_locked_page(False)
        else:
            self._show_locked_page(True)

        try:
            self.reload_tables()
        except Exception as e:
            self.log_error("Startup: reload_tables fehlgeschlagen", e)
        return ok

    # -------------------- Vault-Helfer --------------------
    def _vault_is_open(self) -> bool:
        try:
            if hasattr(self.vault, "is_open") and callable(self.vault.is_open):
                return bool(self.vault.is_open())  # type: ignore
        except Exception:
            pass
        return (getattr(self.vault, "_key", None) is not None and
                getattr(self.vault, "_salt", None) is not None)

    def _vault_try_unlock(self, pwd: str) -> tuple[bool, str | None]:
        last_err = None
        for m in ("unlock", "open", "try_unlock", "check_password"):
            if hasattr(self.vault, m):
                try:
                    _ = getattr(self.vault, m)(pwd)
                    if self._vault_is_open():
                        return True, None
                except Exception as e:
                    last_err = str(e)
        return False, last_err

    def _ensure_vault_open(self) -> bool:
        if self._vault_is_open():
            return True

        vault_path = getattr(self.vault, "path", None)
        file_exists = bool(vault_path and os.path.isfile(vault_path))

        def _try_create(pwd: str) -> bool:
            for m in ("create", "init", "initialize", "set_password"):
                if hasattr(self.vault, m):
                    try:
                        res = getattr(self.vault, m)(pwd)  # type: ignore
                        if res is None or res is True:
                            try:
                                if not hasattr(self.vault, "data") or self.vault.data is None:
                                    self.vault.data = {}
                                self.vault.data.setdefault("accounts", [])
                                self.vault.data.setdefault("settings", {})
                            except Exception:
                                pass
                            getattr(self.vault, "save", lambda: None)()
                            return True
                    except Exception:
                        continue
            ok,_ = self._vault_try_unlock(pwd)
            if ok:
                try:
                    if not hasattr(self.vault, "data") or self.vault.data is None:
                        self.vault.data = {}
                    self.vault.data.setdefault("accounts", [])
                    self.vault.data.setdefault("settings", {})
                    getattr(self.vault, "save", lambda: None)()
                    return True
                except Exception:
                    return False
            return False

        if file_exists:
            pwd, ok = QInputDialog.getText(self, "Vault entsperren", "Master-Passwort:", QLineEdit.Password)
            if not ok or not pwd:
                return False
            ok, _err = self._vault_try_unlock(pwd)
            if ok:
                self._load_from_vault()
                return True
            QMessageBox.critical(self, "Vault", "Entsperren fehlgeschlagen (Passwort falsch oder Datei beschädigt).")
            return False
        else:
            pwd1, ok1 = QInputDialog.getText(self, "Neues Vault", "Neues Master-Passwort:", QLineEdit.Password)
            if not ok1 or not pwd1:
                return False
            pwd2, ok2 = QInputDialog.getText(self, "Neues Vault", "Passwort wiederholen:", QLineEdit.Password)
            if not ok2 or not pwd2:
                return False
            if pwd1 != pwd2:
                QMessageBox.warning(self, "Vault", "Passwörter stimmen nicht überein.")
                return False
            if _try_create(pwd1):
                QMessageBox.information(self, "Vault", "Neues Vault wurde angelegt.")
                return True
            QMessageBox.critical(self, "Vault", "Vault konnte nicht angelegt werden. Bitte prüfe den Pfad in den Einstellungen.")
            return False

    # ==== Speicher-Helfer ====
    def _ensure_vault_dict(self):
        try:
            if not hasattr(self.vault, "data") or self.vault.data is None:
                self.vault.data = {}
            if "accounts" not in self.vault.data or not isinstance(self.vault.data["accounts"], list):
                self.vault.data["accounts"] = []
            if "settings" not in self.vault.data or not isinstance(self.vault.data["settings"], dict):
                self.vault.data["settings"] = {}
        except Exception:
            pass

    # ==== Settings <-> Dict ====
    def _settings_to_dict(self) -> dict:
        s = self.settings
        if hasattr(s, "model_dump"):
            return s.model_dump()               # pydantic v2
        if hasattr(s, "dict"):
            return s.dict()                     # pydantic v1
        return {k: getattr(s, k) for k in dir(s) if not k.startswith("_") and not callable(getattr(s, k, None))}

    def _apply_settings_dict(self, data: dict):
        if not isinstance(data, dict):
            return
        if hasattr(type(self.settings), "model_validate"):
            try:
                self.settings = type(self.settings).model_validate(data)  # pydantic v2
                return
            except Exception:
                pass
        if hasattr(type(self.settings), "parse_obj"):
            try:
                self.settings = type(self.settings).parse_obj(data)       # pydantic v1
                return
            except Exception:
                pass
        for k, v in data.items():
            try:
                setattr(self.settings, k, v)
            except Exception:
                continue

    def _save_vault(self) -> tuple[bool, str | None]:
        last = None
        for m in ("save", "commit", "flush", "write", "persist", "_save_internal"):
            if hasattr(self.vault, m):
                try:
                    getattr(self.vault, m)()
                    return True, None
                except Exception as e:
                    last = str(e)
                    continue
        return False, (last or "Keine passende Save-Methode im Vault gefunden.")

    def _persist_accounts(self) -> bool:
        """Speichert state.accounts sicher ins Vault – ohne replace_accounts()."""
        if not self._ensure_vault_open():
            QMessageBox.warning(self, "Vault gesperrt", "Speichern abgebrochen – Vault ist nicht entsperrt.")
            return False

        accounts = self._accounts_to_dicts()

        try:
            self._ensure_vault_dict()
            self.vault.data["accounts"] = accounts
        except Exception as e:
            vpath = getattr(self.vault, "path", "unbekannt")
            self.log_error(f"Vault: Schreiben in vault.data['accounts'] fehlgeschlagen (Pfad: {vpath})", e)
            QMessageBox.critical(self, "Speichern fehlgeschlagen",
                f"Konnte Accounts nicht in vault.data schreiben.\n\nPfad: {vpath}\nDetails: {e}")
            return False

        ok, err = self._save_vault()
        if not ok:
            vpath = getattr(self.vault, "path", "unbekannt")
            self.log_error(f"Vault: Speichern fehlgeschlagen (Pfad: {vpath})", Exception(err or "n/a"))
            QMessageBox.critical(self, "Speichern fehlgeschlagen",
                f"Konnte Datei nicht sichern.\n\nPfad: {vpath}\nDetails: {err or 'n/a'}")
            return False

        try:
            self.log_msg(f"Gespeichert: {len(accounts)} Accounts")
        except Exception:
            pass
        return True

    # ----------- Vault → State laden (+ Settings) -----------
    def _load_from_vault(self):
        """Liest Accounts + Einstellungen aus dem geöffneten Vault in den State und loggt die Anzahl."""
        try:
            data = getattr(self.vault, "data", {}) or {}

            # --- Einstellungen laden ---
            sdata = data.get("settings")
            if isinstance(sdata, dict) and sdata:
                self._apply_settings_dict(sdata)
                try: self.log_msg("Einstellungen geladen.")
                except Exception: pass

            # --- Accounts laden ---
            accs = data.get("accounts") or []
            loaded = []
            for d in accs:
                try:
                    if hasattr(Account, "from_dict"):
                        a = Account.from_dict(d)  # type: ignore
                    else:
                        game_val = d.get('game', 'valorant')
                        game = Game(game_val) if isinstance(game_val, str) else game_val
                        queue_val = d.get('queue')
                        queue = Queue(queue_val) if queue_val else None
                        a = Account(
                            alias=d.get('alias',''),
                            game=game,
                            region=d.get('region',''),
                            riot_id=d.get('riot_id',''),
                            queue=queue,
                            tier=d.get('tier',''),
                            rr=d.get('rr'),
                            elo=d.get('elo'),
                            kpxc_entry=d.get('kpxc_entry',''),
                            notes=d.get('notes','')
                        )
                        if 'wins' in d: setattr(a, 'wins', d.get('wins'))
                        if 'losses' in d: setattr(a, 'losses', d.get('losses'))
                    loaded.append(a)
                except Exception:
                    continue
            self.state.accounts = loaded
            vpath = getattr(self.vault, "path", "unbekannt")
            self.log_msg(f"Vault geladen: {len(loaded)} Accounts (Datei: {vpath})")
        except Exception as e:
            self.log_error("Vault laden fehlgeschlagen", e)
            QMessageBox.warning(self, "Vault", f"Konnte Daten nicht laden:\n{e}")

    # -------------------- Seiten bauen --------------------
    def _build_main_page(self) -> QWidget:
        page = QWidget()

        self.table_val = DraggableTable(0, 7, on_reordered=self._persist_order)
        self.table_val.setHorizontalHeaderLabels(["Alias","Spiel","Region","Riot ID","Tier","RR","KeePassXC Entry"])

        self.table_lol = DraggableTable(0, 7, on_reordered=self._persist_order)
        self.table_lol.setHorizontalHeaderLabels(["Alias","Spiel","Region","Riot ID","Queue","Tier","KeePassXC Entry"])

        for t in (self.table_val, self.table_lol):
            t.setIconSize(QSize(ICON_SIZE,ICON_SIZE))
            t.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
            t.setEditTriggers(QAbstractItemView.NoEditTriggers)
            t.setSelectionBehavior(QAbstractItemView.SelectRows)
            t.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            t.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            t.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            hdr = t.horizontalHeader(); hdr.setStretchLastSection(True)
            for i in range(t.columnCount()):
                hdr.setSectionResizeMode(i, QHeaderView.Stretch)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.table_val, "Valorant")
        self.tabs.addTab(self.table_lol, "League of Legends / TFT")

        sidebar = self._build_iconmenu()

        root=QHBoxLayout(page); root.setContentsMargins(8,8,8,8)
        root.addWidget(sidebar, 0); root.addWidget(self.tabs, 1)
        return page

    def _build_locked_page(self) -> QWidget:
        w = QWidget()
        w.setAutoFillBackground(True)
        pal = w.palette()
        bg = pal.color(QPalette.Window)
        bg = QColor(max(0, bg.red()-12), max(0, bg.green()-12), max(0, bg.blue()-12))
        pal.setColor(QPalette.Window, bg)
        w.setPalette(pal)

        v = QVBoxLayout(w); v.setContentsMargins(40,40,40,40); v.setSpacing(16)

        lbl_title = QLabel("🔒  Gesperrt")
        lbl_title.setStyleSheet("font-size:28px; font-weight:800; color:#fff;")
        v.addWidget(lbl_title, 0, Qt.AlignHCenter)

        lbl_hint = QLabel("Zum Entsperren bitte Master-Passwort eingeben.")
        lbl_hint.setStyleSheet("font-size:14px; color:#ddd;")
        v.addWidget(lbl_hint, 0, Qt.AlignHCenter)

        row = QHBoxLayout()
        self._unlock_edit = QLineEdit(); self._unlock_edit.setEchoMode(QLineEdit.Password)
        self._unlock_edit.setPlaceholderText("Master-Passwort")
        self._unlock_edit.returnPressed.connect(self._unlock_clicked)
        btn = QPushButton("Entsperren"); btn.clicked.connect(self._unlock_clicked)
        self._unlock_msg = QLabel(""); self._unlock_msg.setStyleSheet("color:#f88;")
        row.addWidget(self._unlock_edit, 3); row.addWidget(btn, 0)
        v.addLayout(row)
        v.addWidget(self._unlock_msg, 0, Qt.AlignHCenter)
        return w

    def _show_locked_page(self, locked: bool):
        self.is_locked = locked
        self.stack.setCurrentIndex(1 if locked else 0)
        if locked:
            try:
                self.table_val.clearSelection(); self.table_lol.clearSelection()
            except Exception:
                pass

    # -------------------- Linkes Menü --------------------
    def _btn(self, icon: QIcon, text: str, handler) -> QToolButton:
        btn = QToolButton(); btn.setText(text); btn.setIcon(icon); btn.setIconSize(QSize(LEFT_ICON_PX,LEFT_ICON_PX))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setCursor(Qt.PointingHandCursor); btn.setFixedHeight(36)
        btn.clicked.connect(handler); return btn

    def _header(self, title: str) -> QLabel:
        lbl = QLabel(title.upper()); lbl.setStyleSheet("color:#bbb; font-weight:700; letter-spacing:1px; font-size:11px;"); return lbl

    def _sep(self) -> QFrame:
        s = QFrame(); s.setFrameShape(QFrame.HLine); s.setFrameShadow(QFrame.Sunken); return s

    def _build_iconmenu(self) -> QWidget:
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(10,10,10,10); lay.setSpacing(8)
        w.setStyleSheet(
            "QToolButton{ color:#fff; background:transparent; padding:6px 10px; border-radius:8px; text-align:left;}"
            "QToolButton:hover{ background:rgba(255,255,255,0.07);}"
            "QToolButton:pressed{ background:rgba(255,255,255,0.14);}"
        )
        # Logo
        logo_w, logo_h = 80, 80
        logo_lbl = QLabel(); logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setFixedSize(80, 80); logo_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        logo_path = os.path.join(base_dir, "resources", "sidebar_logo.png")
        pm = QPixmap(logo_path)
        canvas = QPixmap(logo_w, logo_h); canvas.fill(w.palette().color(QPalette.Window))
        if not pm.isNull():
            scaled = pm.scaled(logo_w, logo_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p = QPainter(canvas); x = (logo_w - scaled.width()) // 2; y = (logo_h - scaled.height()) // 2
            p.drawPixmap(x, y, scaled); p.end(); logo_lbl.setPixmap(canvas)
        else:
            logo_lbl.setText("LOGO"); logo_lbl.setStyleSheet("color:#ddd; font-weight:700;")
        lay.addWidget(logo_lbl, 0, Qt.AlignLeft); lay.addWidget(self._sep())

        # Buttons
        lay.addWidget(self._header("Accounts"))
        lay.addWidget(self._btn(_load_menu_icon("add"), "Account hinzufügen", self.add_account))
        lay.addWidget(self._btn(_load_menu_icon("edit"), "Bearbeiten", self.edit_account))
        lay.addWidget(self._btn(_load_menu_icon("delete"), "Löschen", self.delete_account))
        lay.addWidget(self._sep())

        lay.addWidget(self._header("Rankings"))
        lay.addWidget(self._btn(_load_menu_icon("refresh"), "Ranks aktualisieren", self.refresh_selected))
        lay.addWidget(self._btn(_load_menu_icon("refresh_all"), "Alle aktualisieren", self.refresh_all))
        lay.addWidget(self._sep())

        lay.addWidget(self._header("Login"))
        lay.addWidget(self._btn(_load_menu_icon("login"), "Login (ausgewählt)", self.login_selected))
        lay.addWidget(self._sep())

        lay.addWidget(self._header("Vault & Daten"))
        lay.addWidget(self._btn(_load_menu_icon("export"), "Export", self.export_vault))
        lay.addWidget(self._btn(_load_menu_icon("import"), "Import", self.import_vault))
        lay.addWidget(self._sep())

        lay.addWidget(self._header("System"))
        lay.addWidget(self._btn(_load_menu_icon("settings"), "Einstellungen", self.open_settings))
        lay.addWidget(self._btn(_load_menu_icon("log"), "Log anzeigen", self.show_log))
        lay.addWidget(self._btn(_load_menu_icon("lock"), "Lock", self.lock))
        lay.addStretch(1); w.setFixedWidth(260); return w

    # -------------------- Tabellen/State --------------------
    def current_table(self) -> QTableWidget:
        return self.table_val if self.tabs.currentIndex()==0 else self.table_lol

    def _accounts_to_dicts(self):
        out=[]
        for a in self.state.accounts:
            out.append({
                "alias":a.alias, "game":a.game.value, "region":a.region, "riot_id":a.riot_id,
                "queue":a.queue.value if a.queue else None, "tier":a.tier, "rr":a.rr,
                "elo":a.elo, "kpxc_entry":a.kpxc_entry, "notes":a.notes,
                "wins": getattr(a, "wins", None), "losses": getattr(a, "losses", None),
            })
        return out

    def _table_for_account(self, acc: Account) -> QTableWidget:
        return self.table_val if acc.game==Game.valorant else self.table_lol

    def _add_row(self, table: QTableWidget, acc: Account):
        if table is self.table_val:
            cols=[acc.alias,acc.game.value,acc.region,acc.riot_id,acc.tier, "" if acc.rr is None else str(acc.rr), acc.kpxc_entry]
            row=table.rowCount(); table.insertRow(row)
            for c, text in enumerate(cols):
                item=QTableWidgetItem(text)
                if c==4:
                    try:
                        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                        override = _valorant_icon_path_for_tier(base_dir, acc.tier)
                        icon_path = override or get_rank_icon(acc.game.value, acc.tier, self.settings)
                        if icon_path and os.path.exists(icon_path):
                            pm = QPixmap(icon_path)
                            if not pm.isNull():
                                item.setIcon(QIcon(pm))
                    except Exception as e:
                        self.log_error(f"Icon-Resolve-Fehler (Valorant) für Tier '{acc.tier}'", e)
                item.setData(USER_ROLE_KEY, _row_key(acc)); table.setItem(row,c,item)
        else:
            row=table.rowCount(); table.insertRow(row)
            cols=[acc.alias,acc.game.value,acc.region,acc.riot_id,acc.queue.value if acc.queue else "",acc.tier,acc.kpxc_entry]
            for c, text in enumerate(cols):
                item=QTableWidgetItem(text)
                if c==5:
                    try:
                        icon_path=get_rank_icon(acc.game.value, acc.tier, self.settings)
                        if icon_path and os.path.exists(icon_path):
                            item.setIcon(QIcon(icon_path))
                    except Exception as e:
                        self.log_error(f"Icon-Resolve-Fehler (LoL/TFT) für Tier '{acc.tier}'", e)
                item.setData(USER_ROLE_KEY, _row_key(acc)); table.setItem(row,c,item)

    def _selected_key(self) -> Optional[str]:
        table = self.current_table(); sel = table.selectionModel().selectedRows()
        if not sel: return None
        row = sel[0].row(); item = table.item(row,0)
        return item.data(USER_ROLE_KEY) if item else None

    def _account_by_key(self, key: str) -> Optional[Account]:
        for a in self.state.accounts:
            if _row_key(a)==key: return a
        return None

    def _table_order(self, table: QTableWidget) -> List[str]:
        keys = []
        for r in range(table.rowCount()):
            it = table.item(r,0)
            if it: keys.append(it.data(USER_ROLE_KEY))
        return keys

    def _persist_order(self, *_args):
        map_acc: Dict[str,Account] = { _row_key(a): a for a in self.state.accounts }
        ordered = []
        for k in self._table_order(self.table_val):
            if k in map_acc: ordered.append(map_acc[k])
        for k in self._table_order(self.table_lol):
            if k in map_acc: ordered.append(map_acc[k])
        for a in self.state.accounts:
            if a not in ordered: ordered.append(a)
        self.state.accounts = ordered
        self._persist_accounts()

    def reload_tables(self):
        try:
            if self.is_locked:
                return
        except Exception:
            pass
        self.table_val.setRowCount(0); self.table_lol.setRowCount(0)
        for acc in self.state.accounts:
            t = self._table_for_account(acc); self._add_row(t, acc)

    # -------------------- Aktionen --------------------
    def show_log(self):
        self.log.show(); self.log.raise_(); self.log.activateWindow()

    def add_account(self):
        dlg=AddEditDialog(self)
        if dlg.exec()==QDialog.Accepted:
            acc=dlg.get_account()
            if acc:
                self.state.accounts.append(acc)
                if self._persist_accounts():
                    self._add_row(self._table_for_account(acc), acc)

    def edit_account(self):
        key=self._selected_key()
        if not key: return
        acc=self._account_by_key(key)
        if not acc: return
        dlg=AddEditDialog(self, acc)
        if dlg.exec()==QDialog.Accepted:
            new_acc=dlg.get_account()
            if new_acc:
                idx = self.state.accounts.index(acc)
                self.state.accounts[idx]=new_acc
                if self._persist_accounts():
                    self.reload_tables()

    def delete_account(self):
        key=self._selected_key()
        if not key: return
        acc=self._account_by_key(key)
        if not acc: return
        if QMessageBox.question(self,"Löschen","Account wirklich löschen?")==QMessageBox.Yes:
            self.state.accounts.remove(acc)
            if self._persist_accounts():
                self.reload_tables()

    def _update_rank(self, acc: Account)->tuple[bool,str]:
        try:
            if acc.game==Game.valorant:
                tier, rr, *_ = fetch_valorant_rank(acc.riot_id, acc.region, self.settings)
                acc.tier, acc.rr, acc.elo = tier or "", rr, None
            else:
                tier, lp = fetch_lol_tft_rank(acc, self.settings); acc.tier, acc.elo, acc.rr = tier, lp, None
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def refresh_selected(self):
        key=self._selected_key()
        if not key:
            QMessageBox.warning(self,"Hinweis","Bitte einen Account auswählen."); return
        acc=self._account_by_key(key)
        if not acc:
            QMessageBox.critical(self,"Fehler","Konnte Account nicht finden."); return
        self.log_msg(f"Aktualisiere: {acc.alias} ({acc.game.value}) ...")
        ok,msg=self._update_rank(acc)
        if ok:
            self.log_msg(" → Erfolg")
            if self._persist_accounts():
                self.reload_tables()
        else:
            self.log_error(f"Rank-Update fehlgeschlagen für {acc.alias} ({acc.game.value})", Exception(msg))
            QMessageBox.critical(self,"Rank-Update fehlgeschlagen",msg)

    def refresh_all(self):
        if not self.state.accounts:
            QMessageBox.information(self,"Hinweis","Keine Accounts vorhanden.")
            return
        prog=QProgressDialog("Aktualisiere Ranks...","Abbrechen",0,len(self.state.accounts),self)
        prog.setWindowTitle("Alle aktualisieren"); prog.setMinimumDuration(0)
        for i, acc in enumerate(self.state.accounts, start=1):
            if prog.wasCanceled(): break
            prog.setValue(i-1); prog.setLabelText(f"{acc.alias} ({acc.game.value})")
            self.log_msg(f"Aktualisiere: {acc.alias} ({acc.game.value}) ...")
            ok,msg=self._update_rank(acc)
            if ok: self.log_msg(" → Erfolg")
            else:
                self.log_error(f" → Fehler bei {acc.alias} ({acc.game.value})", Exception(msg))
        prog.setValue(len(self.state.accounts))
        self._persist_accounts()
        self.reload_tables()

    def login_selected(self):
        key=self._selected_key()
        if not key:
            QMessageBox.warning(self,"Hinweis","Bitte einen Account auswählen."); return
        acc=self._account_by_key(key)
        if not acc: return

        # Riot Client sicher starten (nur Client, kein Spiel)
        if self.settings.riot_client_path:
            start_riot(self.settings.riot_client_path, acc.game.value, log=self.log_msg)
        focus_riot_login_window(log=self.log_msg)

        # Username-Feld fokussieren/prüfen
        try:
            ok_focus = focus_username_field(log=self.log_msg)
        except Exception as e:
            ok_focus = False
            self.log_error("focus_username_field() schlug fehl", e)
        if not ok_focus:
            self.log_msg("Hinweis: Benutzername-Feld konnte nicht eindeutig fokussiert werden. "
                         "Falls Auto-Type nicht greift, klicke in das Feld und wiederhole den Login.")

        # KeePassXC Auto-Type
        try:
            if acc.kpxc_entry and acc.kpxc_entry.strip():
                self.log_msg(f"KeePassXC: gezielter Auto-Type für Eintrag: {acc.kpxc_entry}")
                autotype_entry(self.settings.auto_type_hotkey, acc.kpxc_entry.strip())
            else:
                self.log_msg("KeePassXC: globaler Auto-Type")
                trigger_autotype(self.settings.auto_type_hotkey)
        except Exception as e:
            self.log_error("KeePassXC Auto-Type fehlgeschlagen", e)
            QMessageBox.critical(self,"KeePassXC",f"Auto-Type fehlgeschlagen:\n{e}")
            return

        # Sicherheit: nur Login-Phase, kein Spielstart
        try:
            ensure_login_only(duration=8.0, kill=True, log=self.log_msg)
        except Exception as e:
            self.log_error("ensure_login_only() Fehlermeldung", e)

    # ---------- Lock / Unlock ----------
    def lock(self):
        try:
            if hasattr(self.vault, "lock"):
                self.vault.lock()
            if hasattr(self.vault, "clear_cache"):
                self.vault.clear_cache()
        except Exception as e:
            self.log_error("Vault lock() / clear_cache() Fehler", e)
        self._show_locked_page(True)

    def _unlock_clicked(self):
        pwd = self._unlock_edit.text()
        if not pwd:
            self._unlock_msg.setText("Bitte ein Passwort eingeben.")
            return

        ok, err = self._vault_try_unlock(pwd)
        if ok:
            try:
                self._load_from_vault()
            except Exception as e:
                self.log_error("Unlock: Laden aus Vault fehlgeschlagen", e)
            self._unlock_msg.setText("")
            self._unlock_edit.setText("")
            self._show_locked_page(False)
            self.reload_tables()
            return

        vpath = getattr(self.vault, "path", "unbekannt")
        hint = f" (Datei: {vpath})" if vpath else ""
        self._unlock_msg.setText(
            (f"Passwort falsch oder Entsperren fehlgeschlagen{hint}."
             + (f"\nDetails: {err}" if err else ""))
        )
        self.log_msg(f"Unlock fehlgeschlagen{hint}: {err or ''}", level="WARNING")

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings, self.vault)
        if dlg.exec() == QDialog.Accepted:
            # 1) UI -> Objekt
            self.settings = dlg.get_settings()
            # 2) Objekt -> Vault
            try:
                self._ensure_vault_dict()
                self.vault.data["settings"] = self._settings_to_dict()
                ok, err = self._save_vault()
                if not ok:
                    raise RuntimeError(err or "Unbekannter Fehler beim Speichern.")
                QMessageBox.information(self, "Gespeichert", "Einstellungen gespeichert.")
                try: self.log_msg("Einstellungen gespeichert.")
                except Exception: pass
            except Exception as e:
                self.log_error("Einstellungen speichern fehlgeschlagen", e)
                QMessageBox.critical(self, "Speichern fehlgeschlagen", str(e))

    def export_vault(self):
        path,_=QFileDialog.getSaveFileName(self,"Vault exportieren","vault.dat","Vault (*.dat);;Alle Dateien (*)")
        if not path: return
        try:
            shutil.copy2(self.vault.path, path)
            QMessageBox.information(self,"Export","Vault exportiert.")
        except Exception as e:
            self.log_error("Vault-Export fehlgeschlagen", e)
            QMessageBox.critical(self,"Export fehlgeschlagen", str(e))

    def import_vault(self):
        path,_=QFileDialog.getOpenFileName(self,"Vault importieren","","Vault (*.dat);;Alle Dateien (*)")
        if not path: return
        try:
            shutil.copy2(path, self.vault.path)
            QMessageBox.information(self,"Import","Vault importiert. Bitte App neu starten.")
        except Exception as e:
            self.log_error("Vault-Import fehlgeschlagen", e)
            QMessageBox.critical(self,"Import fehlgeschlagen", str(e))

    def closeEvent(self, e):
        # Failsafe: Settings persistieren
        try:
            self._ensure_vault_dict()
            self.vault.data["settings"] = self._settings_to_dict()
            ok, _ = self._save_vault()
            if not ok:
                self.log_msg("Warnung: Speichern beim Beenden nicht bestätigt.", level="WARNING")
            else:
                self.log_msg("Anwendung wird beendet – Daten persistiert.")
        except Exception as ex:
            self.log_error("Speichern beim Beenden fehlgeschlagen", ex)
        super().closeEvent(e)


class DraggableTable(QTableWidget):
    def __init__(self, *a, on_reordered=None, **kw):
        super().__init__(*a, **kw)
        self.on_reordered = on_reordered
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDragDropMode(QAbstractItemView.InternalMove)

    def dropEvent(self, event):
        super().dropEvent(event)
        if self.on_reordered:
            self.on_reordered(self)
