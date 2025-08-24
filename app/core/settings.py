
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional

class Settings(BaseModel):
    riot_client_path: str = Field("", description="Pfad zu RiotClientServices.exe")
    auto_type_hotkey: str = Field("ctrl+alt+k", description="KeePassXC Auto-Type Hotkey")
    ddragon_cdn_base: str = Field("https://ddragon.leagueoflegends.com/cdn", description="LoL DataDragon CDN")
    ddragon_version: str = Field("14.13.1", description="LoL Patch-Version für Emblems")
    valorant_api_base: str = Field("https://valorant-api.com/v1", description="Valorant-API Basis (nur Icons)")
    henrikdev_api_base: str = Field("https://api.henrikdev.xyz", description="HenrikDev Basis-URL")
    default_region: str = Field("eu", description="Standardregion")
    riot_api_key: Optional[str] = None
    henrikdev_api_key: Optional[str] = None
    icon_cache_dir: str = Field("", description="Cache-Ordner (leer = Standard)")

    class Config:
        extra = "ignore"
