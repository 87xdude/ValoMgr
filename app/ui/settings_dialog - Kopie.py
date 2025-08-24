
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, QFileDialog, QMessageBox)
from ..core.settings import Settings
class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings: Settings | None = None):
        super().__init__(parent); self.setWindowTitle("Einstellungen"); self.setModal(True)
        self.riot_client_path=QLineEdit(); self.auto_type_hotkey=QLineEdit(); self.ddragon_cdn_base=QLineEdit(); self.ddragon_version=QLineEdit()
        self.valorant_api_base=QLineEdit(); self.henrikdev_api_base=QLineEdit(); self.default_region=QLineEdit(); self.riot_api_key=QLineEdit(); self.henrikdev_api_key=QLineEdit(); self.icon_cache_dir=QLineEdit()
        form=QFormLayout()
        row=QHBoxLayout(); row.addWidget(self.riot_client_path); b=QPushButton("..."); b.clicked.connect(self.browse_riot); row.addWidget(b); form.addRow("RiotClientServices.exe",row)
        form.addRow("Auto-Type Hotkey", self.auto_type_hotkey); form.addRow("DataDragon Base", self.ddragon_cdn_base); form.addRow("DataDragon Version", self.ddragon_version)
        form.addRow("Valorant API Base", self.valorant_api_base); form.addRow("HenrikDev API Base", self.henrikdev_api_base)
        form.addRow("Standardregion", self.default_region); form.addRow("Riot API Key", self.riot_api_key); form.addRow("HenrikDev API Key", self.henrikdev_api_key); form.addRow("Icon Cache Ordner", self.icon_cache_dir)
        ok=QPushButton("Speichern"); cancel=QPushButton("Abbrechen"); ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        hl=QHBoxLayout(); hl.addStretch(1); hl.addWidget(ok); hl.addWidget(cancel)
        root=QVBoxLayout(); root.addLayout(form); root.addLayout(hl); self.setLayout(root)
        if settings:
            self.riot_client_path.setText(settings.riot_client_path or ""); self.auto_type_hotkey.setText(settings.auto_type_hotkey or "")
            self.ddragon_cdn_base.setText(settings.ddragon_cdn_base or ""); self.ddragon_version.setText(settings.ddragon_version or "")
            self.valorant_api_base.setText(settings.valorant_api_base or ""); self.henrikdev_api_base.setText(settings.henrikdev_api_base or "")
            self.default_region.setText(settings.default_region or ""); self.riot_api_key.setText(settings.riot_api_key or ""); self.henrikdev_api_key.setText(settings.henrikdev_api_key or ""); self.icon_cache_dir.setText(settings.icon_cache_dir or "")
    def browse_riot(self):
        path,_=QFileDialog.getOpenFileName(self,"RiotClientServices.exe auswählen","","Executables (*.exe);;Alle Dateien (*)")
        if path: self.riot_client_path.setText(path)
    def get_settings(self)->Settings:
        return Settings(riot_client_path=self.riot_client_path.text().strip(), auto_type_hotkey=self.auto_type_hotkey.text().strip() or "ctrl+alt+k",
                        ddragon_cdn_base=self.ddragon_cdn_base.text().strip() or "https://ddragon.leagueoflegends.com/cdn",
                        ddragon_version=self.ddragon_version.text().strip() or "14.13.1",
                        valorant_api_base=self.valorant_api_base.text().strip() or "https://valorant-api.com/v1",
                        henrikdev_api_base=self.henrikdev_api_base.text().strip() or "https://api.henrikdev.xyz",
                        default_region=self.default_region.text().strip() or "eu", riot_api_key=self.riot_api_key.text().strip() or None,
                        henrikdev_api_key=self.henrikdev_api_key.text().strip() or None, icon_cache_dir=self.icon_cache_dir.text().strip() or "")
