#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from random import Random
from typing import Dict, List, Optional

from model import NPC
from planning import DailyPlanner, ScheduledActivity


class BehaviorDecisionEngine:
    def __init__(self, planner: DailyPlanner, rng: Random, job_work_actions: Dict[str, List[str]], action_defs: Dict[str, Dict[str, object]]):
        self.planner = planner
        self.rng = rng
        self.job_work_actions = job_work_actions
        self.action_defs = action_defs
        self.job_action_defs: Dict[str, List[Dict[str, object]]] = {
            job_name: [self.action_defs[action_name] for action_name in action_names if action_name in self.action_defs]
            for job_name, action_names in self.job_work_actions.items()
        }

    def activity_for_hour(self, hour: int) -> ScheduledActivity:
        return self.planner.activity_for_hour(hour)

    def set_activity(self, npc: NPC, category: str, detail: str) -> None:
        npc.current_activity = category
        npc.current_action_detail = detail
        npc.status.current_action = f"{category}:{detail}" if detail else category

    def pick_work_action(self, npc: NPC) -> Optional[str]:
        action_defs = self.job_action_defs.get(npc.traits.job.value, [])
        if not action_defs:
            return None
        chosen = self.rng.choice(action_defs)
        name = str(chosen.get("name", "")).strip()
        return name or None

    def resolve_action_def(self, npc: NPC, action_name: str) -> Optional[Dict[str, object]]:
        # 직업별 조인 결과 내 액션만 허용
        for row in self.job_action_defs.get(npc.traits.job.value, []):
            if str(row.get("name", "")).strip() == action_name:
                return row
        return None

    def ensure_work_actions_selected(self, npcs: List[NPC], hour: int, is_hostile_fn) -> None:
        if self.activity_for_hour(hour) != ScheduledActivity.WORK:
            return
        for npc in npcs:
            if npc.status.hp <= 0 or is_hostile_fn(npc):
                continue
            if npc.current_work_action is None:
                npc.current_work_action = self.pick_work_action(npc)
                npc.work_ticks_remaining = 0
            detail = npc.current_work_action or "업무선택실패"
            self.set_activity(npc, "업무", detail)

    def set_meal_state(self, npc: NPC) -> None:
        self.set_activity(npc, "식사", "식사")

    def set_sleep_state(self, npc: NPC) -> None:
        self.set_activity(npc, "취침", "취침")

    def set_dead_state(self, npc: NPC) -> None:
        self.set_activity(npc, "사망", "사망")

    def set_wander_state(self, npc: NPC) -> None:
        self.set_activity(npc, "배회", "배회")
