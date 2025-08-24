
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

class Game(str, Enum):
    valorant = "Valorant"
    lol = "League of Legends"
    tft = "Teamfight Tactics"

class Queue(str, Enum):
    solo = "Solo (LoL)"
    flex = "Flex (LoL)"
    tft = "TFT Ranked"
    tft_pairs = "TFT Pairs"

@dataclass
class Account:
    alias: str
    game: Game
    region: str = ""
    riot_id: str = ""
    queue: Queue | None = None
    tier: str = ""
    rr: Optional[int] = None
    elo: Optional[int] = None
    kpxc_entry: str = ""
    notes: str = ""

@dataclass
class AppState:
    accounts: List[Account] = field(default_factory=list)
