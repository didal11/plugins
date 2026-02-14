#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, MutableMapping

from model import NPC


@dataclass
class EconomySnapshot:
    total_money: int
    market_food_stock: int
    crafted_stock: int


class EconomySystem:
    def __init__(self, job_defs: List[Dict[str, object]], sim_settings: Dict[str, float], item_defs: List[Dict[str, object]], entities: List[Dict[str, object]]):
        self.job_defs = {str(j.get("job")): j for j in job_defs if isinstance(j, dict)}
        self.sim_settings = sim_settings
        self.item_defs = item_defs
        self.entities = entities

    def _resolve_price(self, item: str) -> int:
        base = {
            "wheat": 3, "bread": 7, "fish": 8, "meat": 10, "herb": 5, "potion": 16,
            "ore": 11, "ingot": 18, "wood": 8, "lumber": 12, "hide": 9, "leather": 15, "artifact": 24,
        }
        return int(base.get(item, 8))

    def _market_inventory(self, bstate: MutableMapping[str, object]) -> MutableMapping[str, int]:
        shop = bstate.get("잡화점")
        return getattr(shop, "inventory") if shop is not None else {}

    def _pharmacy_inventory(self, bstate: MutableMapping[str, object]) -> MutableMapping[str, int]:
        ph = bstate.get("약국")
        return getattr(ph, "inventory") if ph is not None else {}

    def _resource_entity_stock(self, name: str) -> int:
        for e in self.entities:
            if str(e.get("type")) == "resource" and str(e.get("name")) == name:
                return int(e.get("stock", 0))
        return -1

    def _consume_resource_entity(self, name: str, amount: int) -> None:
        for e in self.entities:
            if str(e.get("type")) == "resource" and str(e.get("name")) == name:
                e["stock"] = max(0, int(e.get("stock", 0)) - amount)
                return

    def _has_workbench(self, name: str) -> bool:
        if not name:
            return True
        for e in self.entities:
            if str(e.get("type")) == "workbench" and str(e.get("name")) == name:
                return True
        return False

    def run_hour(self, npcs: List[NPC], bstate: MutableMapping[str, object], logs: List[str]) -> EconomySnapshot:
        market = self._market_inventory(bstate)
        pharmacy = self._pharmacy_inventory(bstate)

        for npc in npcs:
            if npc.status.hp <= 0 or getattr(npc.traits, "is_hostile", False):
                continue

            for item in self.item_defs:
                key = str(item.get("key", ""))
                if not key:
                    continue
                # 채집
                if bool(item.get("is_gatherable", False)) and npc.status.fatigue < 95:
                    amount = max(0, int(item.get("gather_amount", 0)))
                    fatigue = max(0, int(item.get("gather_fatigue", 0)))
                    spot = str(item.get("gather_spot", ""))
                    stock = self._resource_entity_stock(spot)
                    if amount > 0 and (stock < 0 or stock >= amount):
                        npc.inventory[key] = int(npc.inventory.get(key, 0)) + amount
                        npc.status.fatigue += fatigue
                        if stock >= 0:
                            self._consume_resource_entity(spot, amount)

                # 조합
                if bool(item.get("is_craftable", False)) and npc.status.fatigue < 95:
                    craft_inputs = item.get("craft_inputs", {}) if isinstance(item.get("craft_inputs", {}), dict) else {}
                    if not self._has_workbench(str(item.get("craft_station", ""))):
                        continue
                    ok = True
                    for in_key, req in craft_inputs.items():
                        if int(npc.inventory.get(str(in_key), 0)) < int(req):
                            ok = False
                            break
                    if ok:
                        for in_key, req in craft_inputs.items():
                            npc.inventory[str(in_key)] = int(npc.inventory.get(str(in_key), 0)) - int(req)
                            if npc.inventory[str(in_key)] <= 0:
                                npc.inventory.pop(str(in_key), None)
                        out = max(0, int(item.get("craft_amount", 0)))
                        npc.inventory[key] = int(npc.inventory.get(key, 0)) + out
                        npc.status.fatigue += max(0, int(item.get("craft_fatigue", 0)))

            # 직업 판매 규칙
            cfg = self.job_defs.get(getattr(npc.traits.job, "value", ""), {})
            sellable = cfg.get("sell_items", []) if isinstance(cfg.get("sell_items"), list) else []
            limit = max(1, int(cfg.get("sell_limit", 3)))
            earned = 0
            sold = 0
            for k in sellable:
                have = int(npc.inventory.get(str(k), 0))
                if have <= 0:
                    continue
                take = min(have, limit)
                npc.inventory[str(k)] = have - take
                if npc.inventory[str(k)] <= 0:
                    npc.inventory.pop(str(k), None)
                market[str(k)] = int(market.get(str(k), 0)) + take
                earned += take * self._resolve_price(str(k))
                sold += take
            if earned > 0:
                npc.status.money += earned
                logs.append(f"{npc.traits.name}: 판매 {sold}개 +{earned}G")

            if npc.status.hunger >= 60:
                for food in ("bread", "fish", "meat", "wheat"):
                    cost = self._resolve_price(food)
                    if int(market.get(food, 0)) > 0 and npc.status.money >= cost:
                        market[food] = int(market.get(food, 0)) - 1
                        npc.status.money -= cost
                        npc.status.hunger = max(0, npc.status.hunger - int(self.sim_settings.get("meal_hunger_restore", 30)))
                        break

            if npc.status.hp < npc.status.max_hp * 0.6 and int(pharmacy.get("potion", 0)) > 0 and npc.status.money >= self._resolve_price("potion"):
                pharmacy["potion"] = int(pharmacy.get("potion", 0)) - 1
                npc.status.money -= self._resolve_price("potion")
                npc.status.hp = min(npc.status.max_hp, npc.status.hp + int(self.sim_settings.get("potion_heal", 14)))

        total_money = sum(max(0, int(n.status.money)) for n in npcs)
        market_food = sum(int(market.get(k, 0)) for k in ("wheat", "bread", "fish", "meat"))
        crafted_stock = int(market.get("ingot", 0)) + int(market.get("leather", 0)) + int(market.get("potion", 0))
        return EconomySnapshot(total_money=total_money, market_food_stock=market_food, crafted_stock=crafted_stock)
