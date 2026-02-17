#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Data model (Enums + dataclasses).

UI 프레임워크와 독립적인 순수 모델 계층.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# =============================
# Enums
# =============================
class RegionType(Enum):
    VILLAGE = "마을"
    OUTSIDE = "마을 밖"


class ZoneType(Enum):
    MARKET = "시장구역"
    RESIDENTIAL = "주거구역"
    JOB = "직업구역"
    INTERACTION = "상호작용 구역"


class JobType(Enum):
    ADVENTURER = "모험가"
    FARMER = "농부"
    FISHER = "어부"
    BLACKSMITH = "대장장이"
    PHARMACIST = "약사"


class SelectionType(Enum):
    NONE = "none"
    NPC = "npc"
    BUILDING = "building"
    BOARD = "board"


class ModalKind(Enum):
    NONE = "none"
    NPC = "npc"
    BUILDING = "building"
    BOARD = "board"


class BuildingTab(Enum):
    PEOPLE = "현재 인원"
    STOCK = "보유 물품"
    TASK = "작업중"


class NPCTab(Enum):
    TRAITS = "트레잇"
    STATUS = "스테이터스"
    INVENTORY = "인벤토리"


class BoardTab(Enum):
    ENTITIES = "자원 목록"
    INVENTORY = "길드 인벤토리"


@dataclass
class TileRect:
    """타일 좌표계 사각형(UI 비의존)."""

    x: int
    y: int
    w: int
    h: int

    def __iter__(self):
        return iter((self.x, self.y, self.w, self.h))

    def copy(self) -> "TileRect":
        return TileRect(self.x, self.y, self.w, self.h)

    @property
    def centerx(self) -> int:
        return self.x + self.w // 2

    @property
    def centery(self) -> int:
        return self.y + self.h // 2

    def collidepoint(self, px: int, py: int) -> bool:
        return self.x <= int(px) < self.x + self.w and self.y <= int(py) < self.y + self.h

    def inflate(self, dx: int, dy: int) -> "TileRect":
        dx = int(dx)
        dy = int(dy)
        return TileRect(self.x - dx // 2, self.y - dy // 2, self.w + dx, self.h + dy)

    def union_ip(self, other: "TileRect") -> None:
        x0 = min(self.x, other.x)
        y0 = min(self.y, other.y)
        x1 = max(self.x + self.w, other.x + other.w)
        y1 = max(self.y + self.h, other.y + other.h)
        self.x, self.y, self.w, self.h = x0, y0, x1 - x0, y1 - y0

    def clamp_ip(self, bounds: "TileRect") -> None:
        x0 = max(self.x, bounds.x)
        y0 = max(self.y, bounds.y)
        x1 = min(self.x + self.w, bounds.x + bounds.w)
        y1 = min(self.y + self.h, bounds.y + bounds.h)
        if x1 < x0:
            x1 = x0
        if y1 < y0:
            y1 = y0
        self.x, self.y, self.w, self.h = x0, y0, x1 - x0, y1 - y0


# =============================
# World objects
# =============================
@dataclass(frozen=True)
class ItemDef:
    key: str
    display: str


@dataclass
class Building:
    zone: ZoneType
    name: str
    rect_tiles: TileRect

    def contains_tile(self, tx: int, ty: int) -> bool:
        return self.rect_tiles.collidepoint(tx, ty)

    def random_tile_inside(self, rng) -> Tuple[int, int]:
        x0, y0, w, h = self.rect_tiles
        return rng.randint(x0, x0 + w - 1), rng.randint(y0, y0 + h - 1)


@dataclass
class Zone:
    zone_type: ZoneType
    rect_tiles: TileRect
    buildings: List[Building]


@dataclass
class BuildingState:
    inventory: Dict[str, int]
    task: str
    task_progress: int
    last_event: str


# =============================
# NPC objects
# =============================
@dataclass
class Status:
    money: int
    happiness: int
    hunger: int
    fatigue: int
    max_hp: int
    hp: int
    strength: int
    agility: int
    current_action: str = "대기"


@dataclass
class Traits:
    name: str
    race: str
    gender: str
    age: int
    job: JobType
    race_str_bonus: int = 0
    race_agi_bonus: int = 0
    race_hp_bonus: int = 0
    race_speed_bonus: float = 0.0
    is_hostile: bool = False


@dataclass
class NPC:
    traits: Traits
    status: Status
    x: float
    y: float
    path: List[Tuple[int, int]]
    home_building: Building
    location_building: Optional[Building]
    inventory: Dict[str, int]
    target_outside_tile: Optional[Tuple[int, int]]
    target_entity_tile: Optional[Tuple[int, int]] = None
    current_work_action: Optional[str] = None
    work_ticks_remaining: int = 0
    adventurer_board_visited: bool = False
    home_sleep_tile: Optional[Tuple[int, int]] = None
    hunger_tick_buffer: float = 0.0
    fatigue_tick_buffer: float = 0.0
