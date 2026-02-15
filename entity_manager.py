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

    def resolve_target_tile(self, entity_key: str) -> Optional[Tuple[int, int]]:
        ent = self.find_by_key(entity_key)
        if ent is None:
            return None
        if int(ent.get("current_quantity", 0)) <= 0:
            return None
        return int(ent.get("x", 0)), int(ent.get("y", 0))

    def consume(self, entity_key: str, amount: int = 1) -> bool:
        ent = self.find_by_key(entity_key)
        if ent is None:
            return False
        current = max(0, int(ent.get("current_quantity", 0)))
        if current <= 0:
            return False
        consume_amount = max(1, int(amount))
        ent["current_quantity"] = max(0, current - consume_amount)
        self.remove_depleted()
        return True

    def remove_depleted(self) -> None:
        self.entities[:] = [e for e in self.entities if int(e.get("current_quantity", 0)) > 0]

    def spawn(self, entity: Dict[str, object]) -> None:
        self.entities.append(entity)
