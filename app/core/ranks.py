from __future__ import annotations
import time, re, json
from typing import Optional, Tuple
import requests

# ============================================================
# Fehlerklasse
# ============================================================

class RiotHttpError(Exception):
    pass

def _safe_json(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except Exception as e:
        raise RiotHttpError(f"Ungültiges JSON von {resp.url}: {e}")

# ============================================================
# Gemeinsame HTTP-Helper
# ============================================================

def _hdrs_riot(api_key: str) -> dict:
    return {"X-Riot-Token": api_key, "Accept": "application/json"}

def _get_json_riot(url: str, api_key: str, retries: int = 3, backoff: float = 0.5) -> dict:
    last = None
    for i in range(retries):
        r = requests.get(url, headers=_hdrs_riot(api_key), timeout=8)
        if r.status_code == 200:
            return _safe_json(r)
        if r.status_code in (429, 502, 503, 504, 408):
            time.sleep(backoff * (2**i)); last = r; continue
        raise RiotHttpError(f"{url} → HTTP {r.status_code}: {r.text}")
    if last is not None:
        raise RiotHttpError(f"{url} → HTTP {last.status_code}: {last.text}")
    raise RiotHttpError(f"{url} → keine Antwort")

def _hdrs_hd(api_key: str) -> dict:
    return {"Authorization": api_key, "Accept": "application/json"}

def _get_json_hd(url: str, api_key: str, retries: int = 3, backoff: float = 0.5) -> dict:
    last = None
    for i in range(retries):
        r = requests.get(url, headers=_hdrs_hd(api_key), timeout=8)
        if r.status_code == 200:
            return _safe_json(r)
        if r.status_code in (429, 502, 503, 504, 408):
            time.sleep(backoff * (2**i)); last = r; continue
        raise RiotHttpError(f"{url} → HTTP {r.status_code}: {r.text}")
    if last is not None:
        raise RiotHttpError(f"{url} → HTTP {last.status_code}: {last.text}")
    raise RiotHttpError(f"{url} → keine Antwort")

# ============================================================
# Region/Host-Erkennung
# ============================================================

# LoL/TFT: Plattform-Hosts (summoner/league/match etc.)
_PLAT_MAP = {
    "br": "br1", "br1": "br1",
    "eune": "eun1", "eun": "eun1", "eun1": "eun1",
    "euw": "euw1", "euw1": "euw1",
    "jp": "jp1", "jp1": "jp1",
    "kr": "kr",
    "lan": "la1", "la1": "la1",
    "las": "la2", "la2": "la2",
    "na": "na1", "na1": "na1",
    "oce": "oc1", "oc1": "oc1",
    "tr": "tr1", "tr1": "tr1",
    "ru": "ru",
}

_REG_MAP = {
    "americas": {"na","na1","br","br1","lan","la1","las","la2","oce","oc1"},
    "europe":   {"euw","euw1","eune","eun1","tr","tr1","ru"},
    "asia":     {"kr","jp","jp1"},
}

def _platform_from_hint(hint: Optional[str]) -> Optional[str]:
    if not hint: return None
    s = re.sub(r"[^a-z0-9]", "", str(hint).lower())
    # Kurzformen normalisieren
    if s in {"eu", "europe"}: s = "euw"
    return _PLAT_MAP.get(s)

def _regional_from_platform(plat: str) -> str:
    p = plat.lower()
    for reg, members in _REG_MAP.items():
        if p in members: return reg
    return "europe"

def _detect_platform(region_field: Optional[str], riot_id: Optional[str]) -> str:
    # 1) explizite Region
    plat = _platform_from_hint(region_field)
    if plat: return plat
    # 2) #TAG aus RiotID
    if riot_id and "#" in riot_id:
        tag = riot_id.split("#",1)[1]
        plat = _platform_from_hint(tag)
        if plat: return plat
    # 3) Fallback
    return "euw1"

# Valorant (HenrikDev) – Regions
_VALO_TAG_MAP = {
    "eu":"eu","euw":"eu","eune":"eu","tr":"eu","ru":"eu","emea":"eu",
    "na":"na",
    "ap":"ap","sea":"ap","jp":"ap","sg":"ap","oce":"ap",
    "kr":"kr",
    "lan":"latam","la1":"latam","las":"latam","la2":"latam","latam":"latam",
    "br":"br","br1":"br",
}

def _valo_region_from_hint(region_field: Optional[str], riot_id: Optional[str]) -> str:
    if region_field:
        s = re.sub(r"[^a-z0-9]", "", region_field.lower())
        if s.startswith(("euw","eun","tr","ru")): return "eu"
        if s.startswith("na"): return "na"
        if s in ("ap","oce","sea","jp"): return "ap"
        if s == "kr": return "kr"
        if s in ("lan","la1","las","la2","latam"): return "latam"
        if s in ("br","br1"): return "br"
    if riot_id and "#" in riot_id:
        tag = re.sub(r"[^a-z0-9]","", riot_id.split("#",1)[1].lower())
        return _VALO_TAG_MAP.get(tag, "eu")
    return "eu"

def _riot_id_split(riot_id: str) -> Tuple[str, str]:
    if "#" in riot_id:
        n, t = riot_id.split("#", 1)
        return n, t
    return riot_id, ""

# ============================================================
# Valorant (HenrikDev)
# ============================================================

def _ensure_hd_key(settings) -> Tuple[str, str]:
    base = getattr(settings, "henrik_base_url", None) or "https://api.henrikdev.xyz"
    key  = getattr(settings, "henrikdev_api_key", None) or getattr(settings, "henrik_api_key", None)
    if not key:
        raise RiotHttpError("Kein HenrikDev API Key hinterlegt (Einstellungen → HenrikDev API Key).")
    return base.rstrip("/"), key

def fetch_valorant_rank(riot_id: str, region_field: Optional[str], settings) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[int]]:
    """
    Rückgabe: (tier_text, rr, wins, losses)
    """
    base, api_key = _ensure_hd_key(settings)
    name, tag = _riot_id_split(riot_id)
    if not name or not tag:
        raise RiotHttpError("Riot ID muss im Format name#tag vorliegen (z. B. foo#EUW).")

    region = _valo_region_from_hint(region_field, riot_id)

    # v3 bevorzugt
    url_v3 = f"{base}/valorant/v3/mmr/{region}/pc/{requests.utils.quote(name)}/{requests.utils.quote(tag)}"
    try:
        j = _get_json_hd(url_v3, api_key)
        data = j.get("data") or {}
        cur  = data.get("current") or {}
        tier_name = (cur.get("tier") or {}).get("name") or "Unrated"
        rr        = cur.get("rr")
        return tier_name, rr, None, None
    except Exception as e_v3:
        # v2 Fallback
        url_v2 = f"{base}/valorant/v2/mmr/{region}/{requests.utils.quote(name)}/{requests.utils.quote(tag)}"
        try:
            j = _get_json_hd(url_v2, api_key)
            data = j.get("data") or {}
            cur  = data.get("current_data") or {}
            tier_name = cur.get("currenttier_patched") or "Unrated"
            rr        = cur.get("ranking_in_tier")
            return tier_name, rr, None, None
        except Exception as e_v2:
            raise RiotHttpError(f"HenrikDev MMR fehlgeschlagen.\n v3: {e_v3}\n v2: {e_v2}")

# ============================================================
# LoL/TFT (offizielle Riot-APIs) – jetzt by-PUUID
# ============================================================

def _ensure_riot_key(settings) -> str:
    key = getattr(settings, "riot_api_key", None) or getattr(settings, "riotKey", None)
    if not key:
        raise RiotHttpError("Kein Riot API Key in den Einstellungen hinterlegt.")
    return key

def _account_by_riot_id(regional: str, name: str, tag: str, api_key: str) -> dict:
    url = f"https://{regional}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{requests.utils.quote(name)}/{requests.utils.quote(tag)}"
    return _get_json_riot(url, api_key)

def _lol_entries_by_puuid(plat: str, puuid: str, api_key: str) -> list:
    # NEU: /lol/league/v4/entries/by-puuid/{encryptedPUUID}
    url = f"https://{plat}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    return _get_json_riot(url, api_key)

def _tft_entries_by_puuid(plat: str, puuid: str, api_key: str) -> list:
    # NEU: /tft/league/v1/by-puuid/{encryptedPUUID}
    url = f"https://{plat}.api.riotgames.com/tft/league/v1/by-puuid/{puuid}"
    return _get_json_riot(url, api_key)

def _pick_lol_queue(entries: list, wanted: Optional[str]) -> Optional[dict]:
    qmap = {"solo": "RANKED_SOLO_5x5", "flex": "RANKED_FLEX_SR"}
    pref = qmap.get((wanted or "").lower())
    if pref:
        for e in entries:
            if e.get("queueType") == pref:
                return e
    for e in entries:
        if e.get("queueType") == "RANKED_SOLO_5x5": return e
    for e in entries:
        if e.get("queueType") == "RANKED_FLEX_SR": return e
    return entries[0] if entries else None

def _pick_tft_queue(entries: list, wanted: Optional[str]) -> Optional[dict]:
    alias = (wanted or "").lower()
    if alias in ("pairs","doubleup","duo","duoqueue"):
        order = ["RANKED_TFT_PAIRS","RANKED_TFT","RANKED_TFT_TURBO"]
    elif alias in ("hyper","turbo","hyp"):
        order = ["RANKED_TFT_TURBO","RANKED_TFT","RANKED_TFT_PAIRS"]
    else:
        order = ["RANKED_TFT","RANKED_TFT_PAIRS","RANKED_TFT_TURBO"]
    for q in order:
        for e in entries:
            if e.get("queueType")==q:
                return e
    return entries[0] if entries else None

def _tier_lp_from_entry(entry: Optional[dict]) -> Tuple[str, Optional[int]]:
    if not entry: return "UNRANKED", None
    tier = (entry.get("tier") or "UNRANKED").title()
    rank = entry.get("rank") or ""
    lp   = entry.get("leaguePoints")
    return (f"{tier} {rank}".strip(), lp)

def fetch_lol_tft_rank(acc, settings) -> Tuple[str, Optional[int]]:
    """
    Holt Tier + LP für LoL/TFT per *PUUID*-Endpoints (SummonerID nicht mehr nötig).
    Erwartet: acc.game in {"lol","tft"}, acc.riot_id "name#tag", optional acc.region / acc.queue.
    Rückgabe: (tier_text, lp_or_none)
    """
    api_key = _ensure_riot_key(settings)

    # 1) Plattform/Regional ermitteln
    plat = _detect_platform(getattr(acc, "region", None), getattr(acc, "riot_id", None))
    regional = _regional_from_platform(plat)

    # 2) PUUID via account-v1 (regionaler Host)
    name, tag = _riot_id_split(getattr(acc, "riot_id", ""))
    if not name or not tag:
        raise RiotHttpError("Riot ID muss im Format name#tag vorliegen (z. B. foo#EUW).")
    acct = _account_by_riot_id(regional, name, tag, api_key)
    puuid = acct.get("puuid")
    if not puuid:
        raise RiotHttpError(f"account-v1 lieferte keine PUUID. Antwort: {json.dumps(acct, ensure_ascii=False)}")

    # 3) League-Einträge jetzt direkt *by-puuid*
    game_val = getattr(acc, "game", "lol")
    game_str = str(getattr(game_val, "value", game_val)).lower()

    if game_str in ("lol", "league", "league of legends"):
        entries = _lol_entries_by_puuid(plat, puuid, api_key)
        picked  = _pick_lol_queue(entries, getattr(getattr(acc, "queue", None), "value", None))
        return _tier_lp_from_entry(picked)

    else:  # TFT
        entries = _tft_entries_by_puuid(plat, puuid, api_key)
        picked  = _pick_tft_queue(entries, getattr(getattr(acc, "queue", None), "value", None))
        return _tier_lp_from_entry(picked)
