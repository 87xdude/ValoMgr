
from __future__ import annotations
import os, json, time, hashlib
from .vault import APP_DIR
CACHE_DIR = os.path.join(APP_DIR,"cache"); os.makedirs(CACHE_DIR, exist_ok=True)
DEFAULT_TTL=900
def _p(k:str)->str: return os.path.join(CACHE_DIR, hashlib.sha256(k.encode()).hexdigest()+".json")
def get(key:str, ttl:int=DEFAULT_TTL):
    p=_p(key)
    if not os.path.exists(p): return None
    try:
        obj=json.load(open(p,"r",encoding="utf-8"))
        if time.time()-obj["ts"]<=ttl: return obj["data"]
    except Exception: return None
    return None
def set(key:str, data):
    try: json.dump({"ts":time.time(),"data":data}, open(_p(key),"w",encoding="utf-8"))
    except Exception: pass
