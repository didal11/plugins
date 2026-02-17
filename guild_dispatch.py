#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, Iterable, List

from pydantic import BaseModel, ConfigDict

from ldtk_integration import GameEntity, ResourceEntity


_GATHER_ACTION_BY_KEY_PREFIX: Dict[str, str] = {
    "herb": "약초채집",
    "tree": "벌목",
    "ore": "채광",
    "animal": "동물사냥",
    "monster": "몬스터사냥",
}


class GuildIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_name: str
    resource_key: str
    amount: int


class GuildDispatcher:
    """길드 중앙 발행기.

    정책 변수:
    - Stock[R]: 현재 보유량(현재는 발견된 리소스의 current_quantity 합)
    - Available[R]: 가용량(리소스 노드 current_quantity 합)
    - TargetStock[R]
    - TargetAvailable[R]

    발행 규칙(비배타):
    - Available[R] < TargetAvailable[R] -> 탐색 발행
    - Stock[R] < TargetStock[R] -> 채집 발행
    - 채집 발행량은 Available[R]를 초과할 수 없음
    """

    def __init__(self, entities: Iterable[GameEntity]):
        self.resource_keys: List[str] = []
        self.stock_by_key: Dict[str, int] = {}
        self.available_by_key: Dict[str, int] = {}

        for entity in entities:
            if not isinstance(entity, ResourceEntity):
                continue
            key = entity.key.strip().lower()
            if not key:
                continue
            if key not in self.available_by_key:
                self.resource_keys.append(key)
                self.stock_by_key[key] = 0
                self.available_by_key[key] = 0

            current_quantity = max(0, int(entity.current_quantity))
            self.available_by_key[key] += current_quantity
            if bool(entity.is_discovered):
                self.stock_by_key[key] += current_quantity

    @staticmethod
    def _gather_action_name(resource_key: str) -> str:
        key = resource_key.strip().lower()
        for prefix, action in _GATHER_ACTION_BY_KEY_PREFIX.items():
            if key == prefix or key.startswith(f"{prefix}_"):
                return action
        return "채집"

    def issue_for_targets(
        self,
        target_stock_by_key: Dict[str, int],
        target_available_by_key: Dict[str, int],
    ) -> List[GuildIssue]:
        issues: List[GuildIssue] = []

        keys = set(self.resource_keys) | {str(k).strip().lower() for k in target_stock_by_key.keys()} | {
            str(k).strip().lower() for k in target_available_by_key.keys()
        }

        for key in sorted(k for k in keys if k):
            stock = max(0, int(self.stock_by_key.get(key, 0)))
            available = max(0, int(self.available_by_key.get(key, 0)))
            target_stock = max(0, int(target_stock_by_key.get(key, 0)))
            target_available = max(0, int(target_available_by_key.get(key, 0)))

            explore_deficit = max(0, target_available - available)
            if explore_deficit > 0:
                issues.append(
                    GuildIssue(
                        action_name="탐색",
                        resource_key=key,
                        amount=explore_deficit,
                    )
                )

            gather_deficit = max(0, target_stock - stock)
            gather_amount = min(gather_deficit, available)
            if gather_amount > 0:
                issues.append(
                    GuildIssue(
                        action_name=self._gather_action_name(key),
                        resource_key=key,
                        amount=gather_amount,
                    )
                )

        return issues
