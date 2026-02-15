#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from random import Random
from typing import Callable, Dict, List, Optional, Tuple

from behavior_decision import BehaviorDecisionEngine
from entity_manager import EntityManager
from model import Building, BuildingState, JobType, NPC


class ActionExecutor:
    def __init__(
        self,
        rng: Random,
        sim_settings: Dict[str, object],
        items: Dict[str, object],
        item_display_to_key: Dict[str, str],
        action_defs: Dict[str, Dict[str, object]],
        bstate: Dict[str, BuildingState],
        building_by_name: Dict[str, Building],
        entities: List[Dict[str, object]],
        entity_manager: EntityManager,
        behavior: BehaviorDecisionEngine,
        status_clamp: Callable[[NPC], None],
    ):
        self.rng = rng
        self.sim_settings = sim_settings
        self.items = items
        self.item_display_to_key = item_display_to_key
        self.action_defs = action_defs
        self.bstate = bstate
        self.building_by_name = building_by_name
        self.entities = entities
        self.entity_manager = entity_manager
        self.behavior = behavior
        self.status_clamp = status_clamp

    def _required_tool_keys(self, required_tools: object) -> List[str]:
        if not isinstance(required_tools, list):
            return []
        keys: List[str] = []
        for raw in required_tools:
            tool_name = str(raw).strip()
            if not tool_name:
                continue
            if tool_name in self.items:
                keys.append(tool_name)
                continue
            item_key = self.item_display_to_key.get(tool_name)
            if item_key is not None:
                keys.append(item_key)
        return keys

    def resolve_work_destination(
        self,
        npc: NPC,
        random_outside_tile_fn: Callable[[], Tuple[int, int]],
    ) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        action_name = npc.current_work_action or ""
        action = self.action_defs.get(action_name, {})
        entity_key = str(action.get("required_entity", "")).strip() if isinstance(action, dict) else ""
        if entity_key:
            tile = self.entity_manager.resolve_target_tile(entity_key)
            if tile is not None:
                return tile, None
        return None, random_outside_tile_fn()

    def do_eat_at_restaurant(self, npc: NPC) -> str:
        s = npc.status
        st = self.bstate["식당"]
        fee = 12
        if s.money < fee:
            s.happiness -= 3
            s.hunger += 3
            self.status_clamp(npc)
            st.last_event = f"{npc.traits.name} 돈 부족"
            return f"{npc.traits.name}: 식당(돈없음)"
        s.money -= fee
        before = s.hunger
        s.hunger -= int(self.sim_settings.get("meal_hunger_restore", 38.0))
        s.happiness += 3
        s.fatigue += 1
        self.status_clamp(npc)
        for k in ["bread", "meat", "fish"]:
            if st.inventory.get(k, 0) > 0 and self.rng.random() < 0.6:
                st.inventory[k] -= 1
                if st.inventory[k] <= 0:
                    del st.inventory[k]
                break
        st.task = "조리/서빙"
        st.task_progress = (st.task_progress + 15) % 101
        st.last_event = f"{npc.traits.name} 식사"
        self.behavior.set_meal_state(npc)
        return f"{npc.traits.name}: 식사 허기 {before}->{s.hunger}"

    def do_rest_at_home(self, npc: NPC) -> str:
        s = npc.status
        before = s.fatigue
        s.fatigue -= int(self.sim_settings.get("rest_fatigue_restore", 28.0))
        s.hunger += 6
        s.happiness += 2
        self.status_clamp(npc)
        st = self.bstate[npc.home_building.name]
        st.last_event = f"{npc.traits.name} 휴식"
        self.behavior.set_sleep_state(npc)
        return f"{npc.traits.name}: 휴식 피로 {before}->{s.fatigue}"

    def primary_action(self, npc: NPC) -> str:
        action_name = npc.current_work_action
        if action_name is None:
            return f"{npc.traits.name}: 작업(정의 없음)"
        action = self.action_defs.get(action_name, {})
        duration_minutes = max(10, int(action.get("duration_minutes", int(action.get("duration_hours", 1)) * 60)))
        duration_ticks = max(1, duration_minutes // 10)
        if npc.work_ticks_remaining <= 0:
            npc.work_ticks_remaining = duration_ticks

        tool_names = action.get("required_tools", []) if isinstance(action.get("required_tools", []), list) else []
        required_keys = self._required_tool_keys(tool_names)
        missing_tools = [k for k in required_keys if int(npc.inventory.get(k, 0)) <= 0]
        if missing_tools:
            display_names = [self.items[k].display if k in self.items else k for k in missing_tools]
            npc.status.current_action = f"{action_name}(도구부족)"
            return f"{npc.traits.name}: {action_name} 실패(도구 부족: {', '.join(display_names)})"

        npc.work_ticks_remaining = max(0, npc.work_ticks_remaining - 1)
        done_ticks = duration_ticks - npc.work_ticks_remaining

        fatigue_cost = int(action.get("fatigue", 12))
        hunger_cost = int(action.get("hunger", 8))
        per_tick_fatigue = max(0, round(fatigue_cost / duration_ticks))
        per_tick_hunger = max(0, round(hunger_cost / duration_ticks))

        s = npc.status
        s.fatigue += per_tick_fatigue
        s.hunger += per_tick_hunger
        s.happiness -= 1
        self.status_clamp(npc)

        entity_key = str(action.get("required_entity", "")).strip()
        if entity_key and not self.entity_manager.consume(entity_key, 1):
            npc.status.current_action = f"{action_name}(대상없음)"
            return f"{npc.traits.name}: {action_name} 실패(엔티티 소진/없음: {entity_key})"

        target_bstate_name = ""
        if entity_key == "field":
            target_bstate_name = "농장"
        elif entity_key == "fish_spot":
            target_bstate_name = "낚시터"
        elif entity_key == "forge_workbench":
            target_bstate_name = "대장간"
        elif entity_key == "alchemy_table":
            target_bstate_name = "약국"
        if target_bstate_name and target_bstate_name in self.bstate:
            bst = self.bstate[target_bstate_name]
            bst.task = action_name
            bst.task_progress = (bst.task_progress + self.rng.randint(15, 35)) % 101
            bst.last_event = f"{npc.traits.name} {action_name} {done_ticks}/{duration_ticks}"

        if npc.work_ticks_remaining > 0:
            npc.status.current_action = f"{action_name}({done_ticks}/{duration_ticks})"
            return f"{npc.traits.name}: {action_name} 진행 {done_ticks}/{duration_ticks}틱"

        outputs = action.get("outputs", {}) if isinstance(action.get("outputs", {}), dict) else {}
        gained_parts: List[str] = []
        valid_items = set(self.items.keys())
        for item, spec in outputs.items():
            if str(item) not in valid_items:
                continue
            qty = 0
            if isinstance(spec, int):
                qty = max(0, int(spec))
            elif isinstance(spec, dict):
                lo = int(spec.get("min", 0))
                hi = int(spec.get("max", lo))
                if hi < lo:
                    lo, hi = hi, lo
                qty = self.rng.randint(max(0, lo), max(0, hi))
            if qty <= 0:
                continue
            npc.inventory[str(item)] = int(npc.inventory.get(str(item), 0)) + qty
            gained_parts.append(f"{item}+{qty}")

        tool_text = f" 도구:{', '.join([str(x) for x in tool_names])}" if tool_names else ""
        gained_text = ", ".join(gained_parts) if gained_parts else "획득 없음"
        npc.status.current_action = action_name
        npc.current_work_action = None
        npc.work_ticks_remaining = 0
        return f"{npc.traits.name}: {action_name} 완료({gained_text}){tool_text}"

    def profit_action(self, npc: NPC) -> str:
        job = npc.traits.job
        s = npc.status

        if job == JobType.ADVENTURER:
            guild = self.bstate["모험가 길드"]
            moved = 0
            earned = 0
            price = {"meat": 10, "wood": 8, "ore": 12, "potion": 16}
            for k in ["meat", "wood", "ore", "potion"]:
                q = int(npc.inventory.get(k, 0))
                if q <= 0:
                    continue
                take = min(q, 2)
                npc.inventory[k] = q - take
                if npc.inventory[k] <= 0:
                    npc.inventory.pop(k, None)
                guild.inventory[k] = int(guild.inventory.get(k, 0)) + take
                moved += take
                earned += price.get(k, 5) * take
            if moved == 0:
                s.happiness -= 1
                self.status_clamp(npc)
                guild.last_event = f"{npc.traits.name} 납품(없음)"
                return f"{npc.traits.name}: 길드 납품(없음)"
            s.money += earned
            s.happiness += 2
            self.status_clamp(npc)
            guild.task_progress = (guild.task_progress + 12) % 101
            guild.last_event = f"{npc.traits.name} 납품({moved}) +{earned}G"
            return f"{npc.traits.name}: 길드 납품({moved}) +{earned}G"

        if job in (JobType.FARMER, JobType.FISHER):
            shop = self.bstate["잡화점"]
            item = "bread" if job == JobType.FARMER else "fish"
            unit = 6 if job == JobType.FARMER else 7
            q = int(npc.inventory.get(item, 0))
            if q <= 0:
                s.happiness -= 1
                self.status_clamp(npc)
                shop.last_event = f"{npc.traits.name} 판매(없음)"
                return f"{npc.traits.name}: 잡화점 판매(없음)"
            sell = min(q, 3)
            npc.inventory[item] = q - sell
            if npc.inventory[item] <= 0:
                npc.inventory.pop(item, None)
            shop.inventory[item] = int(shop.inventory.get(item, 0)) + sell
            gained = unit * sell
            s.money += gained
            s.happiness += 1
            self.status_clamp(npc)
            shop.task_progress = (shop.task_progress + 10) % 101
            shop.last_event = f"{npc.traits.name} 판매({item} {sell}) +{gained}G"
            return f"{npc.traits.name}: 잡화점 판매(+{gained}G)"

        if job == JobType.BLACKSMITH:
            smith = self.bstate["대장간"]
            item = "ore"
            unit = 12
            q = int(npc.inventory.get(item, 0))
            if q <= 0:
                s.happiness -= 1
                self.status_clamp(npc)
                smith.last_event = f"{npc.traits.name} 판매(없음)"
                return f"{npc.traits.name}: 대장간 판매(없음)"
            sell = min(q, 2)
            npc.inventory[item] = q - sell
            if npc.inventory[item] <= 0:
                npc.inventory.pop(item, None)
            smith.inventory[item] = int(smith.inventory.get(item, 0)) + sell
            gained = unit * sell
            s.money += gained
            s.happiness += 1
            self.status_clamp(npc)
            smith.task_progress = (smith.task_progress + 10) % 101
            smith.last_event = f"{npc.traits.name} 판매({sell}) +{gained}G"
            return f"{npc.traits.name}: 대장간 판매(+{gained}G)"

        if job == JobType.PHARMACIST:
            pharm = self.bstate["약국"]
            item = "potion"
            unit = 18
            q = int(npc.inventory.get(item, 0))
            if q <= 0:
                s.happiness -= 1
                self.status_clamp(npc)
                pharm.last_event = f"{npc.traits.name} 판매(없음)"
                return f"{npc.traits.name}: 약국 판매(없음)"
            sell = min(q, 2)
            npc.inventory[item] = q - sell
            if npc.inventory[item] <= 0:
                npc.inventory.pop(item, None)
            pharm.inventory[item] = int(pharm.inventory.get(item, 0)) + sell
            gained = unit * sell
            s.money += gained
            s.happiness += 1
            self.status_clamp(npc)
            pharm.task_progress = (pharm.task_progress + 10) % 101
            pharm.last_event = f"{npc.traits.name} 판매({sell}) +{gained}G"
            return f"{npc.traits.name}: 약국 판매(+{gained}G)"

        return f"{npc.traits.name}: 수익창출(대기)"
