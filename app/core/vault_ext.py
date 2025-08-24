
from __future__ import annotations

def change_password(vault, current_password: str, new_password: str):
    """
    Try to change the vault's master password in a compatible way.
    - If the vault exposes 'set_password', use it.
    - Else, if it has 'password' attribute, set it.
    - Then call 'save()' to persist.
    If the vault exposes a 'password' (or '_password') and the current_password is provided,
    do a soft check to avoid accidental changes.
    """
    # Soft verification when possible
    cur_attr = getattr(vault, "password", None)
    if cur_attr is None:
        cur_attr = getattr(vault, "_password", None)
    if cur_attr is not None and current_password not in (None, ""):
        # compare plain if available (best-effort)
        if cur_attr != current_password:
            # If the vault stores derived/hashed, we can't verify here; raise a clear hint
            raise ValueError("Aktuelles Passwort ist falsch oder konnte nicht verifiziert werden.")
    # Set new
    if hasattr(vault, "set_password"):
        vault.set_password(new_password)
    else:
        try:
            setattr(vault, "password", new_password)
        except Exception:
            # last resort
            setattr(vault, "_password", new_password)
    # Persist
    if hasattr(vault, "save"):
        vault.save()
    else:
        raise RuntimeError("Vault-Objekt hat keine save()-Methode; Änderung konnte nicht gespeichert werden.")
