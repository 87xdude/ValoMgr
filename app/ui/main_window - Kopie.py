
from __future__ import annotations
import os, shutil
from typing import Optional, Dict, List
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPalette
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QProgressDialog, QDialog,
    QHeaderView, QSizePolicy, QLabel, QFrame, QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize

from ..core.models import Account, AppState, Game, Queue
from ..core.settings import Settings
from ..core.vault import Vault
from ..core.icons import get_rank_icon
from ..core.riot import start_riot, focus_riot_login_window
from ..core.kpxc import trigger_autotype
from ..core.ranks import fetch_valorant_rank, fetch_lol_tft_rank
from .add_edit_dialog import AddEditDialog
from .settings_dialog import SettingsDialog
from .log_dialog import LogDialog

USER_ROLE_KEY = Qt.UserRole + 1

def _row_key(acc: Account) -> str:
    return f"{acc.game.value}|{acc.alias}|{acc.riot_id}"

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

class CollapsibleSection(QWidget):
    """Simple collapsible section with a header button and animated content area."""
    def __init__(self, title: str, content: QWidget, expanded: bool=True, parent: QWidget|None=None):
        super().__init__(parent)
        self.header = QPushButton(title)
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setStyleSheet(
            "QPushButton{ text-align:left; padding:8px; font-weight:600; }"
            "QPushButton:checked{ background: rgba(255,255,255,0.05);}"
        )
        self.content_wrap = QWidget()
        lay = QVBoxLayout(self.content_wrap); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        lay.addWidget(content)
        self.content_wrap.setVisible(expanded)

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(4)
        root.addWidget(self.header)
        root.addWidget(self.content_wrap)

        self.header.toggled.connect(self._toggle)

    def _toggle(self, checked: bool):
        self.content_wrap.setVisible(checked)

class MainWindow(QMainWindow):
    def __init__(self, vault: Vault, settings: Settings, state: AppState):
        super().__init__()
        self.vault=vault; self.settings=settings; self.state=state; self.log=LogDialog(self)
        self.setWindowTitle("Riot Account Manager"); self.resize(1220,720)

        # Center layout: left sidebar (collapsible sections) + right tabs
        central=QWidget(); self.setCentralWidget(central)

        # ----- RIGHT: tabs with two tables -----
        self.table_lol = DraggableTable(0, 9, on_reordered=self._persist_order)
        self.table_val = DraggableTable(0, 9, on_reordered=self._persist_order)
        for t in (self.table_lol, self.table_val):
            t.setHorizontalHeaderLabels(["Alias","Spiel","Region","Riot ID","Queue","Tier","RR","Elo/LP","KeePassXC Entry"])
            t.setEditTriggers(QAbstractItemView.NoEditTriggers)
            t.setSelectionBehavior(QAbstractItemView.SelectRows)
            t.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            hdr = t.horizontalHeader()
            hdr.setStretchLastSection(True)
            for i in range(t.columnCount()):
                hdr.setSectionResizeMode(i, QHeaderView.Stretch)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.table_val, "Valorant")
        self.tabs.addTab(self.table_lol, "League of Legends / TFT")
        

        # ----- LEFT: sidebar with collapsible groups -----
        sidebar = self._build_sidebar()

        # Root layout
        root=QHBoxLayout(); root.setContentsMargins(8,8,8,8)
        root.addWidget(sidebar, 0); root.addWidget(self.tabs, 1); central.setLayout(root)

        self.reload_tables()

    # ---------- sidebar build ----------
    def _build_sidebar(self) -> QWidget:
        # Buttons
        self.btn_add=QPushButton("Account hinzufügen")
        self.btn_edit=QPushButton("Bearbeiten")
        self.btn_del=QPushButton("Löschen")
        self.btn_refresh_sel=QPushButton("Ranks aktualisieren")
        self.btn_refresh_all=QPushButton("Alle aktualisieren")
        self.btn_login=QPushButton("Login (ausgewählt)")
        self.btn_settings=QPushButton("Einstellungen")
        self.btn_log=QPushButton("Log anzeigen")
        self.btn_export=QPushButton("Export")
        self.btn_import=QPushButton("Import")
        self.btn_lock=QPushButton("Lock")

        # Wire actions
        self.btn_add.clicked.connect(self.add_account)
        self.btn_edit.clicked.connect(self.edit_account)
        self.btn_del.clicked.connect(self.delete_account)
        self.btn_refresh_sel.clicked.connect(self.refresh_selected)
        self.btn_refresh_all.clicked.connect(self.refresh_all)
        self.btn_login.clicked.connect(self.login_selected)
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_log.clicked.connect(self.show_log)
        self.btn_export.clicked.connect(self.export_vault)
        self.btn_import.clicked.connect(self.import_vault)
        self.btn_lock.clicked.connect(self.lock)

        sidebar=QWidget()
        side=QVBoxLayout(sidebar); side.setContentsMargins(8,8,8,8); side.setSpacing(10)

        # --- Fixed-size logo with palette-matched background ---
        logo_w, logo_h = 200, 100
        logo_lbl = QLabel(); logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setFixedSize(logo_w, logo_h); logo_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        logo_path = os.path.join(base_dir, "resources", "sidebar_logo.png")
        pm = QPixmap(logo_path)
        canvas = QPixmap(logo_w, logo_h)
        bg_color = sidebar.palette().color(QPalette.Window)
        canvas.fill(bg_color if isinstance(bg_color, QColor) else QColor(30,30,30))
        if not pm.isNull():
            scaled = pm.scaled(logo_w, logo_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p = QPainter(canvas); x = (logo_w - scaled.width()) // 2; y = (logo_h - scaled.height()) // 2
            p.drawPixmap(x,y,scaled); p.end()
            logo_lbl.setPixmap(canvas)
        else:
            logo_lbl.setText("Logo"); logo_lbl.setStyleSheet("color:#aaa; font-weight:600;")
        side.addWidget(logo_lbl, 0, Qt.AlignCenter)

        side.addWidget(self._sep())

        # Build sections (each section contains a column of buttons)
        sections = [
            ("Accounts",       [self.btn_add, self.btn_edit, self.btn_del], True),
            ("Rankings",       [self.btn_refresh_sel, self.btn_refresh_all], True),
            ("Login",          [self.btn_login], True),
            ("Vault & Daten",  [self.btn_export, self.btn_import], False),
            ("System",         [self.btn_settings, self.btn_log, self.btn_lock], False),
        ]

        for title, buttons, expanded in sections:
            cont = QWidget()
            lay = QVBoxLayout(cont); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
            for b in buttons:
                b.setMinimumHeight(32); b.setCursor(Qt.PointingHandCursor)
                lay.addWidget(b)
            sec = CollapsibleSection(title, cont, expanded=expanded)
            side.addWidget(sec)

        side.addStretch(1)
        sidebar.setFixedWidth(270)
        return sidebar

    def _sep(self)->QFrame:
        s = QFrame(); s.setFrameShape(QFrame.HLine); s.setFrameShadow(QFrame.Sunken)
        return s

    # ---------- helpers for tables ----------
    def current_table(self) -> QTableWidget:
        return self.table_lol if self.tabs.currentIndex()==0 else self.table_val

    def _accounts_to_dicts(self):
        out=[]
        for a in self.state.accounts:
            out.append({
                "alias":a.alias, "game":a.game.value, "region":a.region, "riot_id":a.riot_id,
                "queue":a.queue.value if a.queue else None, "tier":a.tier, "rr":a.rr,
                "elo":a.elo, "kpxc_entry":a.kpxc_entry, "notes":a.notes
            })
        return out

    def _table_for_account(self, acc: Account) -> QTableWidget:
        return self.table_val if acc.game==Game.valorant else self.table_lol

    def _add_row(self, table: QTableWidget, acc: Account):
        row=table.rowCount(); table.insertRow(row)
        cols=[acc.alias,acc.game.value,acc.region,acc.riot_id,acc.queue.value if acc.queue else "",acc.tier,
              "" if acc.rr is None else str(acc.rr), "" if acc.elo is None else str(acc.elo), acc.kpxc_entry]
        for c, text in enumerate(cols):
            item=QTableWidgetItem(text)
            if c==5:
                icon_path=get_rank_icon(acc.game.value, acc.tier, self.settings)
                if icon_path and os.path.exists(icon_path):
                    item.setIcon(QIcon(icon_path))
            item.setData(USER_ROLE_KEY, _row_key(acc))
            table.setItem(row,c,item)

    def _selected_key(self) -> Optional[str]:
        table = self.current_table()
        sel = table.selectionModel().selectedRows()
        if not sel: return None
        row = sel[0].row()
        item = table.item(row,0)
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
        # Rebuild state order: first LoL/TFT (table_lol order), then Valorant (table_val order)
        map_acc: Dict[str,Account] = { _row_key(a): a for a in self.state.accounts }
        ordered = []
        for k in self._table_order(self.table_lol): 
            if k in map_acc: ordered.append(map_acc[k])
        for k in self._table_order(self.table_val):
            if k in map_acc: ordered.append(map_acc[k])
        # Append any missing
        for a in self.state.accounts:
            if a not in ordered: ordered.append(a)
        self.state.accounts = ordered
        # persist vault
        self.vault.replace_accounts(self._accounts_to_dicts()); self.vault.save()

    def reload_tables(self):
        self.table_lol.setRowCount(0); self.table_val.setRowCount(0)
        for acc in self.state.accounts:
            t = self._table_for_account(acc); self._add_row(t, acc)

    # ---------- actions ----------
    def show_log(self): self.log.show(); self.log.raise_(); self.log.activateWindow()
    def log_msg(self, msg:str): self.log.append(msg)

    def add_account(self):
        dlg=AddEditDialog(self)
        if dlg.exec()==QDialog.Accepted:
            acc=dlg.get_account()
            if acc:
                self.state.accounts.append(acc)
                self.vault.replace_accounts(self._accounts_to_dicts()); self.vault.save()
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
                self.vault.replace_accounts(self._accounts_to_dicts()); self.vault.save()
                self.reload_tables()

    def delete_account(self):
        key=self._selected_key()
        if not key: return
        acc=self._account_by_key(key)
        if not acc: return
        if QMessageBox.question(self,"Löschen","Account wirklich löschen?")==QMessageBox.Yes:
            self.state.accounts.remove(acc)
            self.vault.replace_accounts(self._accounts_to_dicts()); self.vault.save()
            self.reload_tables()

    def _update_rank(self, acc: Account)->tuple[bool,str]:
        try:
            if acc.game==Game.valorant:
                tier, rr = fetch_valorant_rank(acc.riot_id, acc.region, self.settings); acc.tier, acc.rr, acc.elo = tier, rr, None
            else:
                tier, lp = fetch_lol_tft_rank(acc, self.settings); acc.tier, acc.elo, acc.rr = tier, lp, None
            return True, "OK"
        except Exception as e: return False, str(e)

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
            self.log_msg(" → Erfolg"); self.vault.replace_accounts(self._accounts_to_dicts()); self.vault.save(); self.reload_tables()
        else:
            self.log_msg(f" → Fehler: {msg}"); QMessageBox.critical(self,"Rank-Update fehlgeschlagen",msg)

    def refresh_all(self):
        if not self.state.accounts: QMessageBox.information(self,"Hinweis","Keine Accounts vorhanden."); return
        prog=QProgressDialog("Aktualisiere Ranks...","Abbrechen",0,len(self.state.accounts),self); prog.setWindowTitle("Alle aktualisieren"); prog.setMinimumDuration(0)
        for i, acc in enumerate(self.state.accounts, start=1):
            if prog.wasCanceled(): break
            prog.setValue(i-1); prog.setLabelText(f"{acc.alias} ({acc.game.value})")
            self.log_msg(f"Aktualisiere: {acc.alias} ({acc.game.value}) ...")
            ok,msg=self._update_rank(acc)
            if ok: self.log_msg(" → Erfolg")
            else: self.log_msg(f" → Fehler: {msg}")
        prog.setValue(len(self.state.accounts)); self.vault.replace_accounts(self._accounts_to_dicts()); self.vault.save(); self.reload_tables()

    def login_selected(self):
        key=self._selected_key()
        if not key: QMessageBox.warning(self,"Hinweis","Bitte einen Account auswählen."); return
        acc=self._account_by_key(key)
        if not acc: return
        if self.settings.riot_client_path: start_riot(self.settings.riot_client_path, acc.game.value)
        focus_riot_login_window()
        try: trigger_autotype(self.settings.auto_type_hotkey)
        except Exception as e: QMessageBox.critical(self,"KeePassXC",f"Auto-Type konnte nicht ausgelöst werden:\n{e}")

    def open_settings(self):
        dlg=SettingsDialog(self, self.settings)
        if dlg.exec()==QDialog.Accepted:
            self.settings=dlg.get_settings(); pdata=self.vault.data; pdata["settings"]=self.settings.model_dump(); self.vault.save(); QMessageBox.information(self,"Gespeichert","Einstellungen gespeichert.")

    def export_vault(self):
        path,_=QFileDialog.getSaveFileName(self,"Vault exportieren","vault.dat","Vault (*.dat);;Alle Dateien (*)")
        if not path: return
        shutil.copy2(self.vault.path, path); QMessageBox.information(self,"Export","Vault exportiert.")

    def import_vault(self):
        path,_=QFileDialog.getOpenFileName(self,"Vault importieren","","Vault (*.dat);;Alle Dateien (*)")
        if not path: return
        shutil.copy2(path, self.vault.path); QMessageBox.information(self,"Import","Vault importiert. Bitte App neu starten.")

    def lock(self):
        self.vault.lock(); QMessageBox.information(self,"Gesperrt","Vault geschlossen. App wird beendet."); self.close()
