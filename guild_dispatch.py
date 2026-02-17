#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

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
    - Stock[R]: 길드 인벤토리 기반 보유량
    - Available[R]: 길드 등록 리소스 기준 월드 가용량(current_quantity 합)
    - TargetStock[R]
    - TargetAvailable[R]

    발행 규칙(비배타):
    - Available[R] < TargetAvailable[R] -> 탐색 발행
    - Stock[R] < TargetStock[R] -> 채집 발행
    - 채집 발행량은 Available[R]를 초과할 수 없음
    """

    def __init__(
        self,
        entities: Iterable[GameEntity],
        *,
        registered_resource_keys: Optional[Iterable[str]] = None,
        stock_by_key: Optional[Dict[str, int]] = None,
    ):
        self.resource_keys: List[str] = []
        self.stock_by_key: Dict[str, int] = {}
        self.available_by_key: Dict[str, int] = {}

        registered: List[str] = []
        seen: set[str] = set()
        apply_registration_filter = registered_resource_keys is not None
        if registered_resource_keys is not None:
            for raw in registered_resource_keys:
                key = str(raw).strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                registered.append(key)

        if apply_registration_filter:
            self.resource_keys.extend(registered)
            for key in registered:
                self.available_by_key[key] = 0
                self.stock_by_key[key] = 0

        allowed = set(registered)
        for entity in entities:
            if not isinstance(entity, ResourceEntity):
                continue
            key = entity.key.strip().lower()
            if not key:
                continue
            if apply_registration_filter and key not in allowed:
                continue
            if key not in self.available_by_key:
                self.resource_keys.append(key)
                self.stock_by_key[key] = 0
                self.available_by_key[key] = 0

            current_quantity = max(0, int(entity.current_quantity))
            self.available_by_key[key] += current_quantity

        provided_stock = stock_by_key or {}
        for key in self.resource_keys:
            self.stock_by_key[key] = max(0, int(provided_stock.get(key, 0)))

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

        for key in sorted(self.resource_keys):
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
