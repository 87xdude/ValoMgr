
from __future__ import annotations
import os, requests, hashlib
from typing import Optional
from .settings import Settings
def icon_cache_dir(settings: Settings)->str:
    d=settings.icon_cache_dir or os.path.join(os.path.expanduser("~"), ".riot_acct_mgr", "icon_cache"); os.makedirs(d, exist_ok=True); return d
def _safe(url:str)->str:
    h=hashlib.sha256(url.encode()).hexdigest()[:16]; name=url.split("/")[-1].split("?")[0]; return f"{h}_{name or 'icon'}.png"
LOL_TIER_MAP={"iron":"Emblem_Iron.png","bronze":"Emblem_Bronze.png","silver":"Emblem_Silver.png","gold":"Emblem_Gold.png","platinum":"Emblem_Platinum.png","emerald":"Emblem_Emerald.png","diamond":"Emblem_Diamond.png","master":"Emblem_Master.png","grandmaster":"Emblem_Grandmaster.png","challenger":"Emblem_Challenger.png"}
def lol_rank_icon_url(tier:str, settings:Settings)->Optional[str]:
    key=(tier or "").lower()
    for k in LOL_TIER_MAP:
        if k in key: return f"{settings.ddragon_cdn_base}/{settings.ddragon_version}/img/ranked/{LOL_TIER_MAP[k]}"
    return None
def valorant_tier_icon_url(tier:str)->Optional[str]:
    key=(tier or "").lower(); ids={"iron":"0","bronze":"3","silver":"6","gold":"9","platinum":"12","diamond":"15","ascendant":"18","immortal":"21","radiant":"24"}
    for k,v in ids.items():
        if k in key: return f"https://media.valorant-api.com/competitivetiers/ef7ec5e8-3e00-4a2f-9a1a-74314f33aee7/{v}/largeicon.png"
    return None
def get_rank_icon(game:str, tier:str, settings:Settings)->Optional[str]:
    url=valorant_tier_icon_url(tier) if "valorant" in game.lower() else lol_rank_icon_url(tier, settings)
    if not url: return None
    target=os.path.join(icon_cache_dir(settings), _safe(url))
    if os.path.exists(target): return target
    try:
        r=requests.get(url,timeout=10); 
        if r.status_code==200: open(target,"wb").write(r.content); return target
    except Exception: pass
    return None
