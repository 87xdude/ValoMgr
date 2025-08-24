
from __future__ import annotations
import time, requests
def request(method, url, *, headers=None, params=None, json=None, data=None, timeout=10, retries=3, backoff=0.6):
    last=None
    for i in range(retries):
        try:
            r=requests.request(method,url,headers=headers,params=params,json=json,data=data,timeout=timeout)
            if r.status_code==429 and i<retries-1:
                try: wait=float(r.headers.get("Retry-After", backoff*(i+1)))
                except: wait=backoff*(i+1)
                time.sleep(wait); continue
            return r
        except Exception as e:
            last=e; time.sleep(backoff*(i+1))
    if last: raise last
