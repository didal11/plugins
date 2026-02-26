#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from enum import Enum
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


class GuildIssueType(str, Enum):
    EXPLORE = "explore"
    PROCURE = "procure"


class GuildIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: GuildIssueType
    action_name: str
    item_key: str
    resource_key: str
    amount: int


class WorkOrderStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


class WorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    recipe_id: str
    issue_type: GuildIssueType = GuildIssueType.PROCURE
    action_name: str
    item_key: str
    resource_key: str
    amount: int
    job: str
    priority: int = 1
    status: WorkOrderStatus = WorkOrderStatus.OPEN
    assignee_npc_name: str = ""
    created_tick: int = 0
    updated_tick: int = 0


class WorkOrderQueue:
    """직업별 큐를 단일 저장소에서 관리하는 큐(필터 기반)."""

    def __init__(self):
        self.orders_by_id: Dict[str, WorkOrder] = {}
        self.open_by_job: Dict[str, List[str]] = {}

    def _enqueue_open(self, order: WorkOrder) -> None:
        q = self.open_by_job.setdefault(order.job, [])
        if order.order_id not in q:
            q.append(order.order_id)

    def _dequeue_open(self, order: WorkOrder) -> None:
        q = self.open_by_job.get(order.job, [])
        self.open_by_job[order.job] = [oid for oid in q if oid != order.order_id]

    def upsert_open_order(
        self,
        *,
        recipe_id: str,
        issue_type: GuildIssueType,
        action_name: str,
        item_key: str,
        resource_key: str,
        amount: int,
        job: str,
        priority: int,
        now_tick: int,
    ) -> WorkOrder:
        order_id = f"{job}:{recipe_id}"
        if order_id in self.orders_by_id:
            row = self.orders_by_id[order_id]
            if row.status == WorkOrderStatus.OPEN:
                row.amount = max(int(row.amount), max(1, int(amount)))
                row.priority = max(int(row.priority), int(priority))
                row.updated_tick = int(now_tick)
                return row
        row = WorkOrder(
            order_id=order_id,
            recipe_id=recipe_id,
            issue_type=issue_type,
            action_name=action_name,
            item_key=item_key,
            resource_key=resource_key,
            amount=max(1, int(amount)),
            job=job,
            priority=max(1, int(priority)),
            status=WorkOrderStatus.OPEN,
            assignee_npc_name="",
            created_tick=int(now_tick),
            updated_tick=int(now_tick),
        )
        self.orders_by_id[row.order_id] = row
        self._enqueue_open(row)
        return row

    def assign_next(self, job: str, npc_name: str) -> Optional[WorkOrder]:
        q = self.open_by_job.get(job, [])
        if not q:
            return None
        ranked = sorted(
            [self.orders_by_id[oid] for oid in q if self.orders_by_id[oid].status == WorkOrderStatus.OPEN],
            key=lambda row: (-int(row.priority), int(row.created_tick), row.order_id),
        )
        if not ranked:
            return None
        row = ranked[0]
        row.status = WorkOrderStatus.ASSIGNED
        row.assignee_npc_name = npc_name
        self._dequeue_open(row)
        return row

    def complete(self, order_id: str, now_tick: int) -> None:
        row = self.orders_by_id.get(order_id)
        if row is None:
            return
        row.status = WorkOrderStatus.DONE
        row.updated_tick = int(now_tick)

    def fail(self, order_id: str, now_tick: int) -> None:
        row = self.orders_by_id.get(order_id)
        if row is None:
            return
        row.status = WorkOrderStatus.FAILED
        row.updated_tick = int(now_tick)

    def open_orders(self, *, job: Optional[str] = None) -> List[WorkOrder]:
        if job is None or not str(job).strip() or str(job).strip() == "전체":
            return [
                row for row in self.orders_by_id.values() if row.status == WorkOrderStatus.OPEN
            ]
        q = self.open_by_job.get(job, [])
        return [self.orders_by_id[oid] for oid in q if self.orders_by_id[oid].status == WorkOrderStatus.OPEN]


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
        count_available_only_discovered: bool = False,
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

            if count_available_only_discovered and not bool(entity.is_discovered):
                current_quantity = 0
            else:
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
                        issue_type=GuildIssueType.EXPLORE,
                        action_name="탐색",
                        item_key=key,
                        resource_key=key,
                        amount=explore_deficit,
                    )
                )

            gather_deficit = max(0, target_stock - stock)
            gather_amount = min(gather_deficit, available)
            if gather_amount > 0:
                issues.append(
                    GuildIssue(
                        issue_type=GuildIssueType.PROCURE,
                        action_name=self._gather_action_name(key),
                        item_key=key,
                        resource_key=key,
                        amount=gather_amount,
                    )
                )

        return issues
