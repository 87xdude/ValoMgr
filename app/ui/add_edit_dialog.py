
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, QPushButton)
from ..core.models import Account, Game, Queue
class AddEditDialog(QDialog):
    def __init__(self, parent=None, account: Account | None = None):
        super().__init__(parent); self.setWindowTitle("Account hinzufügen" if account is None else "Account bearbeiten"); self.setModal(True)
        self.alias=QLineEdit(); self.game=QComboBox(); self.game.addItems([g.value for g in Game])
        self.region=QLineEdit(); self.riot_id=QLineEdit(); self.queue=QComboBox(); self.queue.addItems([q.value for q in Queue])
        self.tier=QLineEdit(); self.rr=QLineEdit(); self.elo=QLineEdit(); self.kpxc_entry=QLineEdit(); self.notes=QTextEdit()
        form=QFormLayout(); form.addRow("Alias",self.alias); form.addRow("Spiel",self.game); form.addRow("Region",self.region)
        form.addRow("Riot ID",self.riot_id); form.addRow("Queue",self.queue); form.addRow("Tier",self.tier); form.addRow("RR",self.rr); form.addRow("Elo/LP",self.elo); form.addRow("KeePassXC Entry",self.kpxc_entry); form.addRow("Notizen",self.notes)
        ok=QPushButton("OK"); cancel=QPushButton("Abbrechen"); ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        hl=QHBoxLayout(); hl.addStretch(1); hl.addWidget(ok); hl.addWidget(cancel)
        root=QVBoxLayout(); root.addLayout(form); root.addLayout(hl); self.setLayout(root)
        if account:
            self.alias.setText(account.alias); self.game.setCurrentText(account.game.value); self.region.setText(account.region); self.riot_id.setText(account.riot_id)
            self.queue.setCurrentText(account.queue.value if account.queue else ""); self.tier.setText(account.tier); self.rr.setText("" if account.rr is None else str(account.rr))
            self.elo.setText("" if account.elo is None else str(account.elo)); self.kpxc_entry.setText(account.kpxc_entry); self.notes.setPlainText(account.notes)
    def get_account(self)->Account|None:
        def as_int(s): 
            try: return int(s) if s.strip() else None
            except: return None
        acc=Account(alias=self.alias.text().strip(), game=Game(self.game.currentText()), region=self.region.text().strip(),
                    riot_id=self.riot_id.text().strip(), queue=Queue(self.queue.currentText()), tier=self.tier.text().strip(),
                    rr=as_int(self.rr.text()), elo=as_int(self.elo.text()), kpxc_entry=self.kpxc_entry.text().strip(), notes=self.notes.toPlainText().strip())
        return acc if acc.alias else None
