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

    현재는 요청한 초기 정책에 맞춰, 존재하는 리소스 엔티티마다
    탐색 1건 + 채집 1건(가용량 상한 적용)을 발행한다.
    """

    def __init__(self, entities: Iterable[GameEntity]):
        self.resource_keys: List[str] = []
        self.available_by_key: Dict[str, int] = {}
        for entity in entities:
            if not isinstance(entity, ResourceEntity):
                continue
            key = entity.key.strip().lower()
            if not key:
                continue
            if key not in self.available_by_key:
                self.resource_keys.append(key)
                self.available_by_key[key] = 0
            self.available_by_key[key] += max(0, int(entity.current_quantity))

    @staticmethod
    def _gather_action_name(resource_key: str) -> str:
        key = resource_key.strip().lower()
        for prefix, action in _GATHER_ACTION_BY_KEY_PREFIX.items():
            if key == prefix or key.startswith(f"{prefix}_"):
                return action
        return "채집"

    def issue_bootstrap_for_all_resources(self) -> List[GuildIssue]:
        issues: List[GuildIssue] = []
        for key in self.resource_keys:
            issues.append(GuildIssue(action_name="탐색", resource_key=key, amount=1))

            gather_amount = min(1, max(0, int(self.available_by_key.get(key, 0))))
            if gather_amount <= 0:
                continue
            issues.append(
                GuildIssue(
                    action_name=self._gather_action_name(key),
                    resource_key=key,
                    amount=gather_amount,
                )
            )
        return issues
