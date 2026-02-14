#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""경제 시스템.

시뮬레이션 본체(village_sim.py)와 분리된 경제 흐름을 담당한다.
- 직업별 생산/가공/판매
- 생활 소비(식량/포션)
- 시장 재고 보정/가격 계수
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, MutableMapping

from model import JobType, NPC


@dataclass
class EconomySnapshot:
    total_money: int
    market_food_stock: int
    crafted_stock: int


class EconomySystem:
    def __init__(self, job_defs: List[Dict[str, object]], sim_settings: Dict[str, float]):
        self.job_defs = {str(j["job"]): j for j in job_defs if isinstance(j, dict) and "job" in j}
        self.sim_settings = sim_settings

    def _job_cfg(self, job: JobType) -> Dict[str, object]:
        return self.job_defs.get(job.value, {})

    def _resolve_price(self, item: str, base_prices: MutableMapping[str, int], scarcity: float) -> int:
        base = int(base_prices.get(item, 8))
        return max(1, int(base * scarcity))

    def _market_inventory(self, bstate: MutableMapping[str, object]) -> MutableMapping[str, int]:
        shop = bstate.get("잡화점")
        if shop is None:
            return {}
        return getattr(shop, "inventory")

    def _restaurant_inventory(self, bstate: MutableMapping[str, object]) -> MutableMapping[str, int]:
        rst = bstate.get("식당")
        if rst is None:
            return {}
        return getattr(rst, "inventory")

    def _pharmacy_inventory(self, bstate: MutableMapping[str, object]) -> MutableMapping[str, int]:
        ph = bstate.get("약국")
        if ph is None:
            return {}
        return getattr(ph, "inventory")

    def run_hour(self, npcs: List[NPC], bstate: MutableMapping[str, object], logs: List[str]) -> EconomySnapshot:
        market = self._market_inventory(bstate)
        restaurant = self._restaurant_inventory(bstate)
        pharmacy = self._pharmacy_inventory(bstate)

        base_prices = {
            "wheat": 3,
            "bread": 7,
            "fish": 8,
            "meat": 10,
            "herb": 5,
            "potion": 16,
            "ore": 11,
            "ingot": 18,
            "wood": 8,
            "lumber": 12,
            "hide": 9,
            "leather": 15,
            "artifact": 24,
        }

        food_stock = sum(int(market.get(k, 0)) for k in ("wheat", "bread", "fish", "meat"))
        scarcity = 1.35 if food_stock < max(8, len(npcs) // 2) else 1.0

        for npc in npcs:
            if npc.status.hp <= 0:
                continue
            cfg = self._job_cfg(npc.traits.job)
            primary = cfg.get("primary_output", {}) if isinstance(cfg.get("primary_output"), dict) else {}
            for item, qty in primary.items():
                q = max(0, int(qty))
                if q == 0:
                    continue
                npc.inventory[item] = int(npc.inventory.get(item, 0)) + q

            needs = cfg.get("input_need", {}) if isinstance(cfg.get("input_need"), dict) else {}
            craft = cfg.get("craft_output", {}) if isinstance(cfg.get("craft_output"), dict) else {}
            can_craft = True
            for item, req in needs.items():
                if int(npc.inventory.get(item, 0)) < int(req):
                    can_craft = False
                    break
            if can_craft and craft:
                for item, req in needs.items():
                    npc.inventory[item] = int(npc.inventory.get(item, 0)) - int(req)
                    if npc.inventory[item] <= 0:
                        npc.inventory.pop(item, None)
                for item, outq in craft.items():
                    npc.inventory[item] = int(npc.inventory.get(item, 0)) + max(0, int(outq))

            # 판매
            sellable = cfg.get("sell_items", []) if isinstance(cfg.get("sell_items"), list) else []
            earned = 0
            sold_cnt = 0
            for item in sellable:
                have = int(npc.inventory.get(str(item), 0))
                if have <= 0:
                    continue
                amount = min(have, max(1, int(cfg.get("sell_limit", 3))))
                npc.inventory[str(item)] = have - amount
                if npc.inventory[str(item)] <= 0:
                    npc.inventory.pop(str(item), None)
                market[str(item)] = int(market.get(str(item), 0)) + amount
                earned += amount * self._resolve_price(str(item), base_prices, scarcity)
                sold_cnt += amount
            if earned > 0:
                npc.status.money += earned
                logs.append(f"{npc.traits.name}: 생산품 판매 {sold_cnt}개 +{earned}G")

            # 기초 소비
            if npc.status.hunger >= 60:
                for food in ("bread", "fish", "meat", "wheat"):
                    if int(market.get(food, 0)) > 0 and npc.status.money >= self._resolve_price(food, base_prices, scarcity):
                        market[food] = int(market.get(food, 0)) - 1
                        npc.status.money -= self._resolve_price(food, base_prices, scarcity)
                        npc.status.hunger = max(0, npc.status.hunger - int(self.sim_settings.get("meal_hunger_restore", 30)))
                        npc.status.happiness = min(100, npc.status.happiness + 2)
                        break

            if npc.status.hp < npc.status.max_hp * 0.6 and int(pharmacy.get("potion", 0)) > 0:
                potion_price = self._resolve_price("potion", base_prices, 1.0)
                if npc.status.money >= potion_price:
                    pharmacy["potion"] = int(pharmacy.get("potion", 0)) - 1
                    npc.status.money -= potion_price
                    npc.status.hp = min(npc.status.max_hp, npc.status.hp + int(self.sim_settings.get("potion_heal", 14)))

        # 식당은 시장의 식재료 일부를 흡수해 조리품 생성
        wheat = int(market.get("wheat", 0))
        fish = int(market.get("fish", 0))
        meat = int(market.get("meat", 0))
        if wheat >= 2:
            market["wheat"] = wheat - 2
            restaurant["bread"] = int(restaurant.get("bread", 0)) + 1
        if fish >= 1:
            market["fish"] = fish - 1
            restaurant["fish"] = int(restaurant.get("fish", 0)) + 1
        if meat >= 1:
            market["meat"] = meat - 1
            restaurant["meat"] = int(restaurant.get("meat", 0)) + 1

        total_money = sum(max(0, int(n.status.money)) for n in npcs)
        crafted_stock = int(market.get("ingot", 0)) + int(market.get("leather", 0)) + int(market.get("lumber", 0))
        market_food = sum(int(market.get(k, 0)) for k in ("wheat", "bread", "fish", "meat"))
        return EconomySnapshot(total_money=total_money, market_food_stock=market_food, crafted_stock=crafted_stock)
