
from __future__ import annotations
from typing import Tuple
def _n(s:str)->str: return (s or "").strip().upper()
def parse_riot_id(riot_id:str)->Tuple[str,str]:
    if not riot_id or "#" not in riot_id: return riot_id or "", ""
    name, tag = riot_id.split("#",1); return name.strip(), tag.strip()
VALORANT_MAP={"EU":"eu","EUW":"eu","EUNE":"eu","TR":"eu","RU":"eu","NA":"na","BR":"br","LAN":"latam","LAS":"latam","AP":"ap","OCE":"ap","SEA":"ap","JP":"ap","KR":"kr"}
LOL_PLATFORM={"EUW":"euw1","EUNE":"eun1","NA":"na1","BR":"br1","LAN":"la1","LAS":"la2","OCE":"oc1","TR":"tr1","RU":"ru","JP":"jp1","KR":"kr","EU":"euw1","SEA":"oc1","AP":"oc1"}
REGIONAL_CLUSTER={"euw1":"europe","eun1":"europe","tr1":"europe","ru":"europe","na1":"americas","br1":"americas","la1":"americas","la2":"americas","oc1":"americas","jp1":"asia","kr":"asia"}
def valorant_region_from(region:str, tag:str)->str: r=_n(region); t=_n(tag); return VALORANT_MAP.get(r) or VALORANT_MAP.get(t) or "eu"
def lol_platform_from(region:str, tag:str)->str: r=_n(region); t=_n(tag); return LOL_PLATFORM.get(r) or LOL_PLATFORM.get(t) or "euw1"
def lol_regional_from_platform(platform:str)->str: return REGIONAL_CLUSTER.get(platform, "europe")
