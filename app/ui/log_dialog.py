
from __future__ import annotations
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Protokoll"); self.resize(700, 420)
        self.text=QTextEdit(); self.text.setReadOnly(True)
        btn=QPushButton("Schließen"); btn.clicked.connect(self.accept)
        layout=QVBoxLayout(); layout.addWidget(self.text); hl=QHBoxLayout(); hl.addStretch(1); hl.addWidget(btn); layout.addLayout(hl); self.setLayout(layout)
    def append(self, msg:str): self.text.append(msg); self.text.ensureCursorVisible()
