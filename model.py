#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Data model (Enums + dataclasses).

2단계 분리 패치: 과분할을 피하려고 enums/dataclass를 한 파일(model.py)로 묶었습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pygame


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


class PlanStage(Enum):
    PRIMARY = "1차행동"
    PROFIT = "수익창출행동"


class SelectionType(Enum):
    NONE = "none"
    NPC = "npc"
    BUILDING = "building"


class ModalKind(Enum):
    NONE = "none"
    NPC = "npc"
    BUILDING = "building"


class BuildingTab(Enum):
    PEOPLE = "현재 인원"
    STOCK = "보유 물품"
    TASK = "작업중"


class NPCTab(Enum):
    TRAITS = "트레잇"
    STATUS = "스테이터스"
    INVENTORY = "인벤토리"


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
    rect_tiles: pygame.Rect  # tile coordinates

    def contains_tile(self, tx: int, ty: int) -> bool:
        return self.rect_tiles.collidepoint(tx, ty)

    def random_tile_inside(self, rng) -> Tuple[int, int]:
        x0, y0, w, h = self.rect_tiles
        return rng.randint(x0, x0 + w - 1), rng.randint(y0, y0 + h - 1)


@dataclass
class Zone:
    zone_type: ZoneType
    rect_tiles: pygame.Rect
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


@dataclass
class Traits:
    name: str
    race: str
    gender: str
    age: int
    # height_cm: int  # 사용 중단
    # weight_kg: int  # 사용 중단
    job: JobType
    # goal: str  # 사용 중단
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
    target_building: Optional[Building]
    location_building: Optional[Building]
    inventory: Dict[str, int]
    stage: PlanStage
    target_outside_tile: Optional[Tuple[int, int]]
