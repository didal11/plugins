#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from random import Random
from typing import Dict, List, Optional, Tuple


class EntityManager:
    def __init__(self, entities: List[Dict[str, object]], rng: Random):
        self.entities = entities
        self.rng = rng

    def find_by_key(self, entity_key: str) -> Optional[Dict[str, object]]:
        key = str(entity_key).strip()
        if not key:
            return None
        for ent in self.entities:
            if str(ent.get("key", "")).strip() == key:
                return ent
        return None

    def _match_key(self, ent: Dict[str, object], entity_key: str) -> bool:
        key = str(entity_key).strip()
        ent_key = str(ent.get("key", "")).strip()
        if not key or not ent_key:
            return False
        return ent_key == key or ent_key.startswith(f"{key}_")

    def candidates_by_key(self, entity_key: str, discovered_only: bool = False) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        for ent in self.entities:
            if not self._match_key(ent, entity_key):
                continue
            if int(ent.get("current_quantity", 0)) <= 0:
                continue
            if discovered_only and not bool(ent.get("is_discovered", False)):
                continue
            out.append(ent)
        return out

    def resolve_target_tile(self, entity_key: str, discovered_only: bool = False) -> Optional[Tuple[int, int]]:
        candidates = self.candidates_by_key(entity_key, discovered_only=discovered_only)
        if not candidates:
            return None
        ent = self.rng.choice(candidates)
        return int(ent.get("x", 0)), int(ent.get("y", 0))

    def consume(self, entity_key: str, amount: int = 1) -> bool:
        candidates = self.candidates_by_key(entity_key, discovered_only=False)
        if not candidates:
            return False
        ent = self.rng.choice(candidates)
        if bool(ent.get("is_workbench", False)):
            return True
        current = max(0, int(ent.get("current_quantity", 0)))
        if current <= 0:
            return False
        consume_amount = max(1, int(amount))
        ent["current_quantity"] = max(0, current - consume_amount)
        self.remove_depleted()
        return True

    def remove_depleted(self) -> None:
        self.entities[:] = [e for e in self.entities if bool(e.get("is_workbench", False)) or int(e.get("current_quantity", 0)) > 0]

    def discover_near(self, center: Tuple[int, int], radius: int = 1) -> Optional[Dict[str, object]]:
        cx, cy = center
        candidates: List[Dict[str, object]] = []
        for ent in self.entities:
            if bool(ent.get("is_workbench", False)):
                continue
            if bool(ent.get("is_discovered", False)):
                continue
            ex = int(ent.get("x", 0))
            ey = int(ent.get("y", 0))
            if abs(ex - cx) <= radius and abs(ey - cy) <= radius:
                candidates.append(ent)
        if not candidates:
            return None
        discovered = self.rng.choice(candidates)
        discovered["is_discovered"] = True
        return discovered

    def spawn(self, entity: Dict[str, object]) -> None:
        self.entities.append(entity)
