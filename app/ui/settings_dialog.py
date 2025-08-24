
from __future__ import annotations
import os
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QLineEdit, QPushButton, QFormLayout, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt
from ..core.settings import Settings
from ..core import vault_ext

class SettingsDialog(QDialog):
    def __init__(self, parent, settings: Settings, vault):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.settings = settings
        self.vault = vault

        self.riot_api = QLineEdit(getattr(settings, "riot_api_key", ""))
        self.hdev_base = QLineEdit(getattr(settings, "henrikdev_api_base", "https://api.henrikdev.xyz"))
        self.hdev_key  = QLineEdit(getattr(settings, "henrikdev_api_key", ""))
        self.dd_base   = QLineEdit(getattr(settings, "data_dragon_base", "https://ddragon.leagueoflegends.com/cdn"))
        self.dd_ver    = QLineEdit(getattr(settings, "data_dragon_version", "14.10.1"))
        self.riot_client = QLineEdit(getattr(settings, "riot_client_path", ""))
        self.auto_type  = QLineEdit(getattr(settings, "auto_type_hotkey", "<CTRL+ALT+A>"))

        riot_row = QWidget(); rr = QHBoxLayout(riot_row); rr.setContentsMargins(0,0,0,0)
        rr.addWidget(self.riot_client); browse = QPushButton("..."); browse.clicked.connect(self.browse_riot); rr.addWidget(browse)

        form = QFormLayout()
        form.addRow("Riot API Key:", self.riot_api)
        form.addRow("HenrikDev API Base:", self.hdev_base)
        form.addRow("HenrikDev API Key:", self.hdev_key)
        form.addRow("DataDragon Base:", self.dd_base)
        form.addRow("DataDragon Version:", self.dd_ver)
        form.addRow("Riot Client Pfad:", riot_row)
        form.addRow("Auto-Type Hotkey:", self.auto_type)

        # Passwort ändern Gruppe
        pwd_box = QGroupBox("Master-Passwort ändern")
        pwd_lay = QFormLayout(pwd_box)
        self.cur_pwd = QLineEdit(); self.cur_pwd.setEchoMode(QLineEdit.Password)
        self.new_pwd = QLineEdit(); self.new_pwd.setEchoMode(QLineEdit.Password)
        self.rep_pwd = QLineEdit(); self.rep_pwd.setEchoMode(QLineEdit.Password)
        pwd_lay.addRow("Aktuelles Passwort:", self.cur_pwd)
        pwd_lay.addRow("Neues Passwort:", self.new_pwd)
        pwd_lay.addRow("Neues Passwort (Wiederholung):", self.rep_pwd)
        btn_change = QPushButton("Passwort ändern"); btn_change.clicked.connect(self.change_password)
        pwd_lay.addRow("", btn_change)

        # Buttons
        btns = QWidget(); hb = QHBoxLayout(btns); hb.setContentsMargins(0,0,0,0)
        ok = QPushButton("OK"); cancel = QPushButton("Abbrechen")
        ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        hb.addStretch(1); hb.addWidget(ok); hb.addWidget(cancel)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(pwd_box)
        root.addStretch(1)
        root.addWidget(btns)

    def browse_riot(self):
        path, _ = QFileDialog.getOpenFileName(self, "Riot Client auswählen", "", "Executable (*.exe);;Alle Dateien (*)")
        if path:
            self.riot_client.setText(path)

    def get_settings(self) -> Settings:
        data = {
            "riot_api_key": self.riot_api.text().strip(),
            "henrikdev_api_base": self.hdev_base.text().strip(),
            "henrikdev_api_key": self.hdev_key.text().strip(),
            "data_dragon_base": self.dd_base.text().strip(),
            "data_dragon_version": self.dd_ver.text().strip(),
            "riot_client_path": self.riot_client.text().strip(),
            "auto_type_hotkey": self.auto_type.text().strip(),
        }
        # Try to rebuild a Settings object from current class
        try:
            return Settings(**data)
        except Exception:
            # fallback: mutate original
            for k,v in data.items():
                setattr(self.settings, k, v)
            return self.settings

    def change_password(self):
        cur = self.cur_pwd.text()
        new = self.new_pwd.text()
        rep = self.rep_pwd.text()
        if not new or len(new) < 4:
            QMessageBox.warning(self, "Ungültig", "Das neue Passwort muss mindestens 4 Zeichen haben."); return
        if new != rep:
            QMessageBox.warning(self, "Ungültig", "Neues Passwort und Wiederholung stimmen nicht überein."); return
        try:
            vault_ext.change_password(self.vault, cur, new)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Passwort konnte nicht geändert werden:\n{e}")
            return
        QMessageBox.information(self, "Erfolg", "Master-Passwort wurde geändert. Bitte merke dir das neue Passwort!")
        # Felder leeren
        self.cur_pwd.clear(); self.new_pwd.clear(); self.rep_pwd.clear()
