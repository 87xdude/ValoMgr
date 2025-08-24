# -*- coding: utf-8 -*-
import os, sys

# Projekt-Root (Elternordner von "app") in sys.path aufnehmen,
# damit absolute Importe wie "from app.main import run" sicher funktionieren
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_pkg_dir, ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

from app.main import run

if __name__ == "__main__":
    run()