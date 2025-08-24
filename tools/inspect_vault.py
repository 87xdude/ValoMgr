# tools/inspect_vault.py
import os, sys, getpass, json, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/inspect_vault.py <Pfad\\zu\\vault.dat>"); sys.exit(2)
    vpath = sys.argv[1]

    try:
        from app.core.vault import Vault
    except Exception as e:
        print("Konnte app.core.vault nicht importieren:", e); sys.exit(1)

    print("[i] Datei:", vpath)
    if not os.path.isfile(vpath):
        print("   → Datei existiert nicht."); sys.exit(2)
    st = os.stat(vpath)
    print(f"    Größe: {st.st_size} bytes, mtime: {datetime.datetime.fromtimestamp(st.st_mtime)}")

    vault = None
    try:
        vault = Vault(vpath)
    except TypeError:
        vault = Vault()

    pwd = getpass.getpass("Master-Passwort: ").strip()

    def is_open(v):
        try:
            return bool(getattr(v, "is_open")())
        except Exception:
            pass
        return (getattr(v, "_key", None) is not None and getattr(v, "_salt", None) is not None)

    # unlock
    ok = False
    for m in ("unlock","open","try_unlock","check_password"):
        if hasattr(vault, m):
            try:
                getattr(vault, m)(pwd)
                if is_open(vault): ok = True; break
            except Exception as e:
                last = str(e)
    if not ok:
        print("   → Entsperren fehlgeschlagen (Passwort/Format?)."); sys.exit(3)

    data = getattr(vault, "data", None)
    if data is None:
        print("   → vault.data ist None / nicht verfügbar."); sys.exit(4)

    print("   Keys in vault.data:", list(data.keys()))
    accs = data.get("accounts")
    if isinstance(accs, list):
        print(f"   accounts: {len(accs)} Einträge")
        for i, a in enumerate(accs[:3], 1):
            print(f"    [{i}] {a.get('alias','?')}  {a.get('game','?')}  {a.get('riot_id','?')}")
    else:
        print("   → Kein 'accounts'-Array gefunden.")
        # Zeig einen Ausschnitt der Struktur (ohne große Blobs)
        preview = {k: (type(v).__name__) for k,v in data.items()}
        print("   Strukturvorschau:", json.dumps(preview, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
