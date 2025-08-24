
from __future__ import annotations
import os, json, base64, secrets
from typing import Dict, Any
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_VAULT_PATH = os.path.join(os.path.expanduser("~"), ".riot_acct_mgr", "vault.dat")
APP_DIR = os.path.dirname(DEFAULT_VAULT_PATH)

def ensure_parent(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

class VaultError(Exception): pass

class Vault:
    def __init__(self, path: str = DEFAULT_VAULT_PATH):
        self.path = path; ensure_parent(self.path)
        self._plaintext: Dict[str, Any] = {}; self._key=None; self._salt=None
    def exists(self)->bool: return os.path.exists(self.path)
    def _derive_key(self, password: str, salt: bytes)->bytes:
        return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))
    def create(self, password: str):
        if self.exists(): raise VaultError("Vault existiert bereits.")
        self._salt = secrets.token_bytes(16); self._key=self._derive_key(password,self._salt)
        self._plaintext={"version":1,"settings":{},"accounts":[]}; self._save_internal()
    def open(self, password: str):
        if not self.exists(): raise VaultError("Vault-Datei nicht gefunden.")
        data=open(self.path,"rb").read(); meta_len=int.from_bytes(data[:4],"big")
        meta=json.loads(data[4:4+meta_len].decode()); ciphertext=data[4+meta_len:]
        self._salt=base64.b64decode(meta["salt"]); nonce=base64.b64decode(meta["nonce"])
        self._key=self._derive_key(password,self._salt); aes=AESGCM(self._key)
        try: pt=aes.decrypt(nonce,ciphertext,None)
        except Exception as e: self._key=None; raise VaultError("Entschlüsselung fehlgeschlagen (Passwort?)") from e
        self._plaintext=json.loads(pt.decode())
    def _save_internal(self):
        if self._key is None or self._salt is None: raise VaultError("Vault ist nicht geöffnet.")
        aes=AESGCM(self._key); nonce=secrets.token_bytes(12)
        pt=json.dumps(self._plaintext,ensure_ascii=False).encode(); ct=aes.encrypt(nonce,pt,None)
        meta={"version":1,"kdf":"scrypt","salt":base64.b64encode(self._salt).decode(),"nonce":base64.b64encode(nonce).decode()}
        m=json.dumps(meta).encode(); out=len(m).to_bytes(4,"big")+m+ct; open(self.path,"wb").write(out)
    def save(self): self._save_internal()
    def lock(self): self._key=None; self._plaintext={}
    @property
    def data(self)->Dict[str,Any]: return self._plaintext
    def set_settings(self, s:Dict[str,Any]): self._plaintext["settings"]=s
    def get_settings(self)->Dict[str,Any]: return self._plaintext.get("settings",{})
    def get_accounts(self)->list[dict]: return list(self._plaintext.get("accounts",[]))
    def replace_accounts(self, a:list[dict]): self._plaintext["accounts"]=a
