#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Arcade-first village simulator runtime.

이 모듈은 기존 pygame 루프를 폐기하고 아래 스택으로 단순화했다.
- rendering/runtime: arcade
- world source: LDtk(optional)
- schema validation: pydantic
- JSON I/O: orjson
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
from random import Random
from typing import Dict, List, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field

from editable_data import (
    DATA_DIR,
    load_action_defs,
    load_item_defs,
    load_job_defs,
    load_monster_templates,
    load_npc_templates,
)
from ldtk_integration import (
    GameEntity,
    GameWorld,
    BuildingEntity,
    NpcStatEntity,
    ResourceEntity,
    StructureEntity,
    WorkbenchEntity,
    build_world_from_ldtk,
)
from guild_dispatch import GuildDispatcher, GuildIssue, GuildIssueType, WorkOrderQueue
from exploration import (
    CellConstructionState,
    GuildBoardExplorationState,
    NPCExplorationBuffer,
    RuntimeCellStateStore,
    choose_next_frontier,
    frontier_cells_from_known_view,
    is_known_from_view,
    record_known_cell_discovery,
)
from planning import DailyPlanner, ScheduledActivity

BOARD_REPORT_ACTION = "게시판보고"
BOARD_CHECK_ACTION = "게시판확인"

try:
    import torch
except ImportError:  # optional dependency
    torch = None

def _has_workbench_trait(entity: GameEntity) -> bool:
    return isinstance(entity, WorkbenchEntity) or entity.key.strip().lower().endswith("_workbench")


def _is_guild_board_entity(entity: GameEntity) -> bool:
    key = entity.key.strip().lower()
    name = entity.name.strip().lower()
    return "게시판" in entity.name or "board" in key or "board" in name


def _format_guild_issue_lines(simulation: "SimulationRuntime") -> List[str]:
    issued = simulation.work_order_queue.open_orders(job=simulation.board_issue_job_filter)
    if not issued:
        return ["발행된 의뢰가 없습니다."]
    out: List[str] = []
    for row in issued:
        display_action = simulation.display_action_name(
            row.action_name,
            row.resource_key,
            issue_type=row.issue_type.value,
            item_key=row.item_key,
        )
        display_resource = simulation.display_item_name(row.item_key)
        out.append(
            f"- [{row.job}] {display_action} | 자원:{display_resource} | 수량:{int(row.amount)} | 우선:{int(row.priority)}"
        )
    return out




def _format_item_catalog_lines() -> List[str]:
    items = [row for row in load_item_defs() if isinstance(row, dict)]
    rows = []
    for row in items:
        key = str(row.get("key", "")).strip()
        display = str(row.get("display", "")).strip()
        if not key:
            continue
        rows.append((key, display or key))
    if not rows:
        return ["표시할 아이템 정의가 없습니다."]
    rows.sort(key=lambda row: row[0])
    return [f"- {display} ({key})" for key, display in rows]

def _pick_entity_near_world_point(
    entities: List[GameEntity],
    world_x: float,
    world_y: float,
    *,
    tile_size: int,
    world_height_px: int,
) -> GameEntity | None:
    threshold = max(8.0, float(tile_size) * 0.55)
    threshold_sq = threshold * threshold

    nearest: GameEntity | None = None
    nearest_sq = float("inf")
    for entity in entities:
        ex = entity.x * tile_size + tile_size / 2
        ey = world_height_px - (entity.y * tile_size + tile_size / 2)
        dist_sq = ((float(world_x) - ex) ** 2) + ((float(world_y) - ey) ** 2)
        if dist_sq > threshold_sq:
            continue
        if dist_sq < nearest_sq:
            nearest_sq = dist_sq
            nearest = entity
    return nearest


def _pick_npc_near_world_point(
    npcs: List[RenderNpc],
    world_x: float,
    world_y: float,
    *,
    tile_size: int,
    world_height_px: int,
) -> RenderNpc | None:
    threshold = max(8.0, float(tile_size) * 0.55)
    threshold_sq = threshold * threshold

    nearest: RenderNpc | None = None
    nearest_sq = float("inf")
    for npc in npcs:
        nx = npc.x * tile_size + tile_size / 2
        ny = world_height_px - (npc.y * tile_size + tile_size / 2)
        dist_sq = ((float(world_x) - nx) ** 2) + ((float(world_y) - ny) ** 2)
        if dist_sq > threshold_sq:
            continue
        if dist_sq < nearest_sq:
            nearest_sq = dist_sq
            nearest = npc
    return nearest


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_width: int = 1280
    window_height: int = 720
    title: str = "Arcade Village Sim"
    camera_speed: float = 520.0
    zoom_min: float = 0.4
    zoom_max: float = 3.0
    zoom_in_step: float = 1.08
    zoom_out_step: float = 0.92
    use_torch_for_npc: bool = False


class CameraState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


class JsonNpc(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    job: str = "농부"
    x: int | None = None
    y: int | None = None
    hp: int | None = None
    strength: int | None = None
    agility: int | None = None
    focus: int | None = None


class RenderNpc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    job: str
    x: int
    y: int
    hp: int = 10
    strength: int = 1
    agility: int = 1
    focus: int = 1


class SimulationNpcState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_action: str = "대기"
    current_action_display: str = "대기"
    ticks_remaining: int = 0
    decision_ticks_until_check: int = 0
    sleep_path_initialized: bool = False
    work_path_initialized: bool = False
    path: List[Tuple[int, int]] = Field(default_factory=list)
    last_board_check_day: int = -1
    board_cycle_checked: bool = False
    board_cycle_needs_report: bool = False
    assigned_order_id: str = ""
    contract_state: str = "NO_CONTRACT"
    contract_execute_state: str = "IDLE"


class SimulationRuntime:
    """렌더 루프와 분리된 고정 틱(1분 단위) 시뮬레이터."""

    TICK_MINUTES = 1
    TICKS_PER_HOUR = 60 // TICK_MINUTES
    DECISION_INTERVAL_TICKS = 10

    def _is_current_level_town(self) -> bool:
        return self.world.level_id.strip().lower() == "town"

    def __init__(
        self,
        world: GameWorld,
        npcs: List[RenderNpc],
        monsters: List[RenderNpc] | None = None,
        tick_seconds: float = 0.1,
        seed: int = 42,
        use_torch_for_npc: bool = False,
    ):
        self.world = world
        self.npcs = npcs
        self.monsters = monsters or []
        self.tick_seconds = max(0.1, float(tick_seconds))
        self._accumulator = 0.0
        self.ticks = 0
        self.rng = Random(seed)
        self.planner = DailyPlanner()
        self.use_torch_for_npc = bool(use_torch_for_npc and torch is not None)

        self.job_actions = self._job_actions_map()
        self.job_procure_items = self._job_procure_items_map()
        self.action_duration_ticks = self._action_duration_map()
        self.action_required_entity = self._action_required_entity_map()
        self.action_schedulable = self._action_schedulable_map()
        self.action_interruptible = self._action_interruptible_map()
        self.guild_inventory_by_key: Dict[str, int] = {}
        self.guild_dispatcher = GuildDispatcher(self.world.entities)
        self.work_order_queue = WorkOrderQueue()
        self.action_candidate_jobs = self._action_candidate_jobs_map()
        self.procure_candidate_jobs_by_item = self._procure_candidate_jobs_by_item_map()
        self.board_issue_job_filter = "전체"
        self.target_stock_by_key, self.target_available_by_key = {}, {}
        self.guild_board_exploration_state = GuildBoardExplorationState()
        self._refresh_guild_dispatcher()
        self.state_by_name: Dict[str, SimulationNpcState] = {
            npc.name: SimulationNpcState() for npc in self.npcs
        }
        self.exploration_buffer_by_name: Dict[str, NPCExplorationBuffer] = {
            npc.name: NPCExplorationBuffer() for npc in self.npcs
        }
        self.minimap_known_cells_snapshot: Set[Tuple[int, int]] = set()
        self.minimap_known_resources_snapshot: Dict[Tuple[str, Tuple[int, int]], int] = {}
        self.minimap_known_monsters_snapshot: Set[Tuple[str, Tuple[int, int]]] = set()
        self.cell_runtime_state = RuntimeCellStateStore()
        self.blocked_tiles = {tuple(row) for row in self.world.blocked_tiles}
        self.dining_tiles = self._find_dining_tiles()
        self.bed_tiles = self._find_bed_tiles()
        self.global_buildings_by_key = self._global_building_registry()
        self._initialize_exploration_state()
        self._recompute_work_orders(reason="init")

    def _global_building_registry(self) -> Dict[str, List[Tuple[int, int]]]:
        out: Dict[str, List[Tuple[int, int]]] = {}
        for entity in self.world.entities:
            if not isinstance(entity, BuildingEntity):
                continue
            key = entity.key.strip().lower()
            if not key:
                continue
            out.setdefault(key, []).append((entity.x, entity.y))
        for key in out:
            out[key].sort()
        return out

    def _dynamic_registered_resource_keys(self) -> List[str]:
        keys: List[str] = []
        seen: set[str] = set()
        for entity in self.world.entities:
            if not isinstance(entity, ResourceEntity):
                continue
            key = entity.key.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys

    def _all_item_keys(self) -> List[str]:
        keys: List[str] = []
        seen: set[str] = set()
        for row in load_item_defs():
            if not isinstance(row, dict):
                continue
            key = str(row.get("key", "")).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys

    def _refresh_guild_dispatcher(self) -> None:
        registered_resources = self._dynamic_registered_resource_keys()
        all_item_keys = self._all_item_keys()
        for key in [*registered_resources, *all_item_keys]:
            if key not in self.guild_inventory_by_key:
                self.guild_inventory_by_key[key] = 0

        self.guild_dispatcher = GuildDispatcher(
            self.world.entities,
            registered_resource_keys=registered_resources,
            stock_by_key=self.guild_inventory_by_key,
            count_available_only_discovered=True,
        )
        known_available = self._known_available_by_key_from_board()
        self.guild_dispatcher.available_by_key = {
            key: int(known_available.get(key, 0))
            for key in self.guild_dispatcher.resource_keys
        }

        target_stock, target_available = self._default_guild_targets()
        stock_keys = set(target_stock.keys()) | set(self.target_stock_by_key.keys()) | set(self.guild_inventory_by_key.keys())
        for key in stock_keys:
            if key not in self.guild_inventory_by_key:
                self.guild_inventory_by_key[key] = 0
        self.target_stock_by_key = {
            key: int(self.target_stock_by_key.get(key, target_stock.get(key, 1)))
            for key in sorted(stock_keys)
        }
        self.target_available_by_key = {
            key: int(self.target_available_by_key.get(key, target_available.get(key, 1)))
            for key in self.guild_dispatcher.resource_keys
        }

    def _default_guild_targets(self) -> Tuple[Dict[str, int], Dict[str, int]]:
        stock_keys = sorted(set(self._all_item_keys()))
        target_stock_by_key = {key: 1 for key in stock_keys}
        target_available_by_key = {key: 1 for key in self.guild_dispatcher.resource_keys}
        return target_stock_by_key, target_available_by_key

    def _action_candidate_jobs_map(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for job, actions in self.job_actions.items():
            for action in actions:
                rows = out.setdefault(action, [])
                if job not in rows:
                    rows.append(job)
        return out

    def board_issue_filter_jobs(self) -> List[str]:
        return ["전체", *sorted(self.job_actions.keys())]

    def _order_recipe_id(self, issue: GuildIssue) -> str:
        return (
            f"{issue.issue_type.value}::"
            f"{issue.action_name.strip()}::"
            f"{issue.item_key.strip().lower()}::"
            f"{issue.resource_key.strip().lower()}"
        )

    def _jobs_for_issue(self, issue: GuildIssue) -> List[str]:
        if issue.issue_type == GuildIssueType.PROCURE:
            item_key = issue.item_key.strip().lower()
            candidates = list(self.procure_candidate_jobs_by_item.get(item_key, []))
            if candidates:
                return candidates
            return list(self.action_candidate_jobs.get(issue.action_name, []))
        return list(self.action_candidate_jobs.get(issue.action_name, []))

    def _recompute_work_orders(self, *, reason: str) -> None:
        issued = self.guild_dispatcher.issue_for_targets(
            self.target_stock_by_key,
            self.target_available_by_key,
        )
        now_tick = int(self.ticks)
        for issue in issued:
            for job in self._jobs_for_issue(issue):
                self.work_order_queue.upsert_open_order(
                    recipe_id=self._order_recipe_id(issue),
                    issue_type=issue.issue_type,
                    action_name=issue.action_name,
                    item_key=issue.item_key,
                    resource_key=issue.resource_key,
                    amount=max(1, int(issue.amount)),
                    job=job,
                    priority=2 if issue.issue_type == GuildIssueType.EXPLORE else 1,
                    now_tick=now_tick,
                )

    def _known_available_by_key_from_board(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for (name, _coord), amount in self.guild_board_exploration_state.known_resources.items():
            key = str(name).strip().lower()
            if not key:
                continue
            out[key] = out.get(key, 0) + max(0, int(amount))
        return out

    def _resource_name_map(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for entity in self.world.entities:
            if not isinstance(entity, ResourceEntity):
                continue
            key = entity.key.strip().lower()
            if not key:
                continue
            out.setdefault(key, entity.name.strip() or key)
        return out

    def display_resource_name(self, resource_key: str) -> str:
        key = resource_key.strip().lower()
        return self._resource_name_map().get(key, key)

    def display_action_name(
        self,
        action_name: str,
        resource_key: str,
        *,
        issue_type: str = "",
        item_key: str = "",
    ) -> str:
        issue_key = issue_type.strip().lower()
        target_key = item_key.strip().lower() or resource_key.strip().lower()
        if issue_key == GuildIssueType.PROCURE.value:
            return f"{self.display_item_name(target_key)} 조달"
        if action_name.strip() == "탐색":
            return f"{self.display_resource_name(resource_key)} 탐색"
        return action_name

    def _find_dining_tiles(self) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for entity in self.world.entities:
            key = entity.key.lower()
            name = entity.name.lower()
            if "dining" in key or "식탁" in name:
                out.append((entity.x, entity.y))
        return out

    def _find_bed_tiles(self) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for entity in self.world.entities:
            key = entity.key.lower()
            name = entity.name.lower()
            if "bed" in key or "침대" in name:
                out.append((entity.x, entity.y))
        return out

    def _town_walkable_cells(self) -> List[Tuple[int, int]]:
        bounds = _town_bounds_tiles(self.world)
        if bounds is None:
            return []
        x0, y0, w, h = bounds
        width_tiles, height_tiles = self._grid_bounds()
        out: List[Tuple[int, int]] = []
        for y in range(y0, y0 + max(1, h)):
            for x in range(x0, x0 + max(1, w)):
                if x < 0 or y < 0 or x >= width_tiles or y >= height_tiles:
                    continue
                if (x, y) in self.blocked_tiles:
                    continue
                out.append((x, y))
        return out

    def _initialize_exploration_state(self) -> None:
        self.guild_board_exploration_state.known_cells.clear()
        town_cells = self._town_walkable_cells()
        self.cell_runtime_state.mark_baseline_completed(town_cells)
        for coord in town_cells:
            self._mark_cell_discovered(coord, force=True)
        for npc in self.npcs:
            self._mark_cell_discovered((npc.x, npc.y), force=True)

    def set_cell_runtime_state(self, coord: Tuple[int, int], state: CellConstructionState) -> bool:
        return self.cell_runtime_state.set_state(coord, state)

    def get_cell_runtime_state(self, coord: Tuple[int, int]) -> CellConstructionState:
        return self.cell_runtime_state.get_state(coord)

    def pop_cell_runtime_state_changes(self) -> Dict[Tuple[int, int], CellConstructionState]:
        return self.cell_runtime_state.pop_pending_changes()

    def _grid_bounds(self) -> Tuple[int, int]:
        width_tiles = max(1, self.world.width_px // self.world.grid_size)
        height_tiles = max(1, self.world.height_px // self.world.grid_size)
        return width_tiles, height_tiles

    def _is_known_from_view(self, coord: Tuple[int, int], buffer: NPCExplorationBuffer) -> bool:
        return is_known_from_view(coord, self.guild_board_exploration_state.known_cells, buffer)

    def _frontier_cells_from_known_view(self, buffer: NPCExplorationBuffer) -> Set[Tuple[int, int]]:
        """Compute frontier cells at runtime from buffer-known cells only.

        frontier 정의: 버퍼 known 셀의 8방향 이웃 중 아직 known이 아닌 셀.
        게시판 확인을 통해 버퍼 known은 전역 known을 포함하게 된다.
        """

        width_tiles, height_tiles = self._grid_bounds()
        return frontier_cells_from_known_view(buffer, self.blocked_tiles, width_tiles, height_tiles)

    def _mark_cell_discovered_to_buffer(
        self,
        buffer: NPCExplorationBuffer,
        coord: Tuple[int, int],
        force: bool = False,
    ) -> None:
        width_tiles, height_tiles = self._grid_bounds()
        record_known_cell_discovery(
            buffer,
            coord,
            self.guild_board_exploration_state.known_cells,
            self.blocked_tiles,
            width_tiles,
            height_tiles,
            force=force,
        )

    def _has_adjacent_known_8(
        self,
        x: int,
        y: int,
        width_tiles: int,
        height_tiles: int,
        buffer: NPCExplorationBuffer,
    ) -> bool:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= width_tiles or ny >= height_tiles:
                    continue
                if self._is_known_from_view((nx, ny), buffer):
                    return True
        return False

    def _flush_exploration_buffer(self, npc_name: str) -> None:
        buffer = self.exploration_buffer_by_name.setdefault(npc_name, NPCExplorationBuffer())
        if not buffer.has_any_delta():
            return
        self.guild_board_exploration_state.apply_npc_buffer(buffer, self.rng)
        buffer.clear()

    @staticmethod
    def _board_check_action_name_in_candidates(candidates: List[str]) -> str | None:
        if BOARD_CHECK_ACTION in candidates:
            return BOARD_CHECK_ACTION
        return None

    @staticmethod
    def _board_report_action_name_in_candidates(candidates: List[str]) -> str | None:
        if BOARD_REPORT_ACTION in candidates:
            return BOARD_REPORT_ACTION
        return None

    @staticmethod
    def _is_board_report_like_action(action_name: str) -> bool:
        return action_name == BOARD_REPORT_ACTION

    @staticmethod
    def _is_board_check_like_action(action_name: str) -> bool:
        return action_name == BOARD_CHECK_ACTION

    def _handle_board_check(self, npc_name: str) -> None:
        buffer = self.exploration_buffer_by_name.setdefault(npc_name, NPCExplorationBuffer())
        delta = self.guild_board_exploration_state.export_delta_for_known_cells(
            self.guild_board_exploration_state.known_cells
        )
        buffer.merge_from(delta)

    def _handle_board_report(self, npc_name: str) -> None:
        self._flush_exploration_buffer(npc_name)
        self.minimap_known_cells_snapshot = set(self.guild_board_exploration_state.known_cells)
        self.minimap_known_resources_snapshot = dict(self.guild_board_exploration_state.known_resources)
        self.minimap_known_monsters_snapshot = set(self.guild_board_exploration_state.known_monsters)

    def _mark_cell_discovered(self, coord: Tuple[int, int], force: bool = False) -> None:
        """Backward-compatible helper used by tests/system flows.

        실제 known/frontier 반영은 버퍼를 통해서만 수행한다.
        """

        system_name = "__system__"
        buffer = self.exploration_buffer_by_name.setdefault(system_name, NPCExplorationBuffer())
        self._mark_cell_discovered_to_buffer(buffer, coord, force=force)
        self._flush_exploration_buffer(system_name)

    def _observe_visible_entities_to_buffer(self, buffer: NPCExplorationBuffer, visible_cells: Set[Tuple[int, int]]) -> None:
        global_known_resources = self.guild_board_exploration_state.known_resources
        for entity in self.world.entities:
            coord = (entity.x, entity.y)
            if coord not in visible_cells:
                continue
            if isinstance(entity, ResourceEntity):
                resource_key = entity.key.strip().lower()
                if int(entity.current_quantity) > 0:
                    buffer.record_resource_observation(
                        resource_key,
                        coord,
                        int(entity.current_quantity),
                        global_known_resources,
                    )
                    entity.is_discovered = True
                else:
                    buffer.record_resource_absence(resource_key, coord, global_known_resources)

        for monster in self.monsters:
            coord = (monster.x, monster.y)
            if coord not in visible_cells:
                continue
            key = monster.name.strip().lower()
            if key:
                buffer.record_monster_discovery(key, coord)


    def _mark_visible_area_discovered(self, npc_name: str, coord: Tuple[int, int]) -> None:
        buffer = self.exploration_buffer_by_name.setdefault(npc_name, NPCExplorationBuffer())
        x, y = coord
        visible_cells: Set[Tuple[int, int]] = set()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                cell = (x + dx, y + dy)
                self._mark_cell_discovered_to_buffer(buffer, cell)
                visible_cells.add(cell)
        self._observe_visible_entities_to_buffer(buffer, visible_cells)

    def _step_exploration_action(
        self,
        npc: RenderNpc,
        state: SimulationNpcState,
        width_tiles: int,
        height_tiles: int,
    ) -> bool:
        buffer = self.exploration_buffer_by_name.setdefault(npc.name, NPCExplorationBuffer())
        self._mark_visible_area_discovered(npc.name, (npc.x, npc.y))

        if not state.work_path_initialized or not state.path:
            frontier_view = self._frontier_cells_from_known_view(buffer)
            target = choose_next_frontier(frontier_view, self.rng)
            if target is None:
                return False
            state.path = self._find_path_to_nearest_target(
                (npc.x, npc.y),
                [target],
                width_tiles,
                height_tiles,
            )
            state.work_path_initialized = True
            if not state.path:
                return False

        next_x, next_y = state.path.pop(0)
        npc.x, npc.y = next_x, next_y
        self._mark_visible_area_discovered(npc.name, (npc.x, npc.y))
        return True

    @staticmethod
    def _duration_to_ticks(minutes: object) -> int:
        try:
            parsed = int(minutes)
        except Exception:
            parsed = 1
        return max(1, parsed)

    def _job_actions_map(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for row in load_job_defs():
            if not isinstance(row, dict):
                continue
            job = str(row.get("job", "")).strip()
            if not job:
                continue
            actions = [str(x).strip() for x in row.get("work_actions", []) if str(x).strip()]
            if actions:
                out[job] = actions
        return out

    def _job_procure_items_map(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for row in load_job_defs():
            if not isinstance(row, dict):
                continue
            job = str(row.get("job", "")).strip()
            if not job:
                continue
            items = [str(x).strip().lower() for x in row.get("procure_items", []) if str(x).strip()]
            out[job] = items
        return out

    def _procure_candidate_jobs_by_item_map(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for job, items in self.job_procure_items.items():
            for item_key in items:
                rows = out.setdefault(item_key, [])
                if job not in rows:
                    rows.append(job)
        return out

    def _action_duration_map(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for row in load_action_defs():
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            out[name] = self._duration_to_ticks(row.get("duration_minutes", 10))
        return out

    def _action_required_entity_map(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for row in load_action_defs():
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            out[name] = str(row.get("required_entity", "")).strip()
        return out

    def _action_schedulable_map(self) -> Dict[str, bool]:
        out: Dict[str, bool] = {}
        for row in load_action_defs():
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            out[name] = bool(row.get("schedulable", True))
        return out

    def _action_interruptible_map(self) -> Dict[str, bool]:
        out: Dict[str, bool] = {}
        for row in load_action_defs():
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            out[name] = bool(row.get("interruptible", True))
        return out

    def _producer_actions_by_item_map(self) -> Dict[str, List[str]]:
        """호환성을 위해 아이템별 생산 액션 매핑을 제공한다.

        현재 데이터 소스(`load_item_defs`)는 아이템 키/표시명만 제공하므로
        생산 액션 정보가 없는 경우 빈 매핑을 반환한다.
        """

        return {}

    def _expected_output_by_action_item_map(self) -> Dict[Tuple[str, str], int]:
        """호환성을 위해 (action, item)별 기대 산출량 매핑을 제공한다.

        관련 데이터가 정의되지 않은 환경에서도 런타임 초기화가 실패하지 않도록
        기본값으로 빈 매핑을 사용한다.
        """

        return {}

    def _item_display_name_map(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for row in load_item_defs():
            if not isinstance(row, dict):
                continue
            key = str(row.get("key", "")).strip().lower()
            if not key:
                continue
            display = str(row.get("display", "")).strip() or key
            out.setdefault(key, display)
        return out

    def display_item_name(self, item_key: str) -> str:
        key = item_key.strip().lower()
        item_name = self._item_display_name_map().get(key)
        if item_name:
            return item_name
        return self.display_resource_name(key)

    def _apply_order_completion_effects(self, order_id: str) -> None:
        row = self.work_order_queue.orders_by_id.get(order_id)
        if row is None:
            return
        if row.issue_type == GuildIssueType.EXPLORE:
            return
        key = row.item_key.strip().lower()
        if not key:
            return
        produced = max(1, int(row.amount))
        self.guild_inventory_by_key[key] = max(0, int(self.guild_inventory_by_key.get(key, 0))) + produced

    def _ticks_until_anchor_hour(self, anchor_hour: int) -> int:
        current_tick_of_day = self.ticks % (24 * self.TICKS_PER_HOUR)
        anchor_tick_of_day = (anchor_hour % 24) * self.TICKS_PER_HOUR
        gap = anchor_tick_of_day - current_tick_of_day
        if gap <= 0:
            gap += 24 * self.TICKS_PER_HOUR
        return gap

    def _reserved_adventurer_board_ticks(self, state: SimulationNpcState) -> int:
        reserve = 0
        if not state.board_cycle_checked:
            reserve += self.action_duration_ticks.get(BOARD_CHECK_ACTION, 0)
        if state.board_cycle_needs_report:
            reserve += self.action_duration_ticks.get(BOARD_REPORT_ACTION, 0)
        return reserve

    def _work_duration_for_action(self, action_name: str, npc: RenderNpc, state: SimulationNpcState) -> int:
        default_ticks = self.action_duration_ticks.get(action_name, 1)
        if not self.action_schedulable.get(action_name, True):
            return default_ticks

        gap_ticks = self._ticks_until_anchor_hour(self.planner.dinner_hour)
        if npc.job.strip() == "모험가":
            gap_ticks = max(1, gap_ticks - self._reserved_adventurer_board_ticks(state))
        return max(1, gap_ticks)

    def _can_interrupt_current_action(self, state: SimulationNpcState) -> bool:
        if state.current_action in {"식사", "취침", "대기", "배회"}:
            return True
        if state.ticks_remaining <= 0:
            return True
        return self.action_interruptible.get(state.current_action, True)

    @staticmethod
    def _entity_matches_key(entity: GameEntity, required_key: str) -> bool:
        required_raw = required_key.strip()
        key_raw = entity.key.strip()
        name_raw = entity.name.strip()
        if not required_raw or (not key_raw and not name_raw):
            return False

        def _norm(value: str) -> str:
            return value.lower().replace(" ", "").replace("_", "").replace("-", "")

        required_norm = _norm(required_raw)
        key_norm = _norm(key_raw)
        name_norm = _norm(name_raw)

        if required_raw == key_raw or required_raw == name_raw:
            return True
        if required_raw.lower() == key_raw.lower() or required_raw.lower() == name_raw.lower():
            return True
        if required_norm and (required_norm == key_norm or required_norm == name_norm):
            return True
        return bool(required_norm and key_norm.startswith(required_norm))

    def _find_work_tiles(self, action_name: str) -> List[Tuple[int, int]]:
        # 작업 좌표는 실시간 탐색 결과가 아니라 월드 엔티티 스냅샷(self.world.entities)에서 조회한다.
        # self.world.entities 는 LDtk 로더가 entity px 값을 grid 좌표(x, y)로 변환해 채워 넣은 값이다.
        required_key = self.action_required_entity.get(action_name, "")
        if not required_key:
            return []

        out: List[Tuple[int, int]] = []
        for entity in self.world.entities:
            if not self._entity_matches_key(entity, required_key):
                continue
            if isinstance(entity, ResourceEntity) and entity.current_quantity <= 0:
                continue
            out.append((entity.x, entity.y))
        return out

    def _current_hour(self) -> int:
        hours_elapsed = self.ticks // self.TICKS_PER_HOUR
        return hours_elapsed % 24

    def _pick_next_work_action(self, npc: RenderNpc, state: SimulationNpcState) -> None:
        """업무 시간 업무 선택 로직 (의뢰 계약 상태 중심)."""

        # 이미 계약된 의뢰가 있으면 재계약하지 않고 실행을 이어간다.
        if state.assigned_order_id:
            row = self.work_order_queue.orders_by_id.get(state.assigned_order_id)
            if row is not None:
                state.contract_state = "EXECUTING"
                state.contract_execute_state = "RUNNING"
                action = row.action_name
                state.current_action = action
                state.current_action_display = self.display_action_name(
                    action,
                    row.resource_key,
                    issue_type=row.issue_type.value,
                    item_key=row.item_key,
                )
                state.ticks_remaining = self._work_duration_for_action(action, npc, state)
                state.path = []
                state.work_path_initialized = False
                return
            state.assigned_order_id = ""

        # 계약이 없는 상태에서만 게시판으로 이동해 새 의뢰를 받는다.
        state.contract_state = "GO_BOARD"
        state.contract_execute_state = "IDLE"
        state.current_action = BOARD_CHECK_ACTION
        state.current_action_display = BOARD_CHECK_ACTION
        state.ticks_remaining = self._work_duration_for_action(BOARD_CHECK_ACTION, npc, state)
        state.path = []
        state.work_path_initialized = False


    def _torch_decision_code(self, planned: ScheduledActivity, ticks_remaining: int) -> int:
        if not self.use_torch_for_npc or torch is None:
            if planned == ScheduledActivity.MEAL:
                return 1
            if planned == ScheduledActivity.SLEEP:
                return 2
            if ticks_remaining <= 0:
                return 3
            return 0

        planned_code = 0
        if planned == ScheduledActivity.MEAL:
            planned_code = 1
        elif planned == ScheduledActivity.SLEEP:
            planned_code = 2

        decision = torch.tensor([planned_code, int(ticks_remaining)], dtype=torch.int64)
        if int(decision[0].item()) == 1:
            return 1
        if int(decision[0].item()) == 2:
            return 2
        if int(decision[1].item()) <= 0:
            return 3
        return 0

    def _apply_next_path_step(self, npc: RenderNpc, state: SimulationNpcState) -> bool:
        if not state.path:
            return False
        next_x, next_y = state.path.pop(0)
        if self.use_torch_for_npc and torch is not None:
            pos = torch.tensor([next_x, next_y], dtype=torch.int64)
            npc.x = int(pos[0].item())
            npc.y = int(pos[1].item())
            return True
        npc.x, npc.y = next_x, next_y
        return True

    def _step_random(self, npc: RenderNpc, width_tiles: int, height_tiles: int) -> None:
        candidates = self._neighbors(npc.x, npc.y, width_tiles, height_tiles) + [(npc.x, npc.y)]
        if self.use_torch_for_npc and torch is not None:
            idx = int(torch.randint(0, len(candidates), (1,)).item())
            next_x, next_y = candidates[idx]
        else:
            next_x, next_y = self.rng.choice(candidates)
        npc.x, npc.y = next_x, next_y

    @staticmethod
    def _format_sim_datetime(ticks: int) -> str:
        minutes = max(0, ticks) * SimulationRuntime.TICK_MINUTES
        minute = minutes % 60
        total_hours = minutes // 60
        hour = total_hours % 24
        total_days = total_hours // 24

        year = 0
        month_days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

        def year_days(y: int) -> int:
            leap = (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)
            return 366 if leap else 365

        days_left = total_days
        while days_left >= year_days(year):
            days_left -= year_days(year)
            year += 1

        month = 1
        for idx, md in enumerate(month_days, start=1):
            leap_bonus = 1 if idx == 2 and year_days(year) == 366 else 0
            if days_left < md + leap_bonus:
                month = idx
                break
            days_left -= md + leap_bonus
        day = days_left + 1

        return f"{year:04d}년 {month:02d}월 {day:02d}일 {hour:02d}:{minute:02d}"

    def display_clock(self) -> str:
        return self._format_sim_datetime(self.ticks)

    def display_clock_by_interval(self, interval_minutes: int = 30) -> str:
        safe_interval = max(1, int(interval_minutes))
        total_minutes = max(0, self.ticks) * self.TICK_MINUTES
        rounded_minutes = total_minutes - (total_minutes % safe_interval)
        rounded_ticks = rounded_minutes // self.TICK_MINUTES
        return self._format_sim_datetime(rounded_ticks)

    def _step_npc(self, npc: RenderNpc) -> None:
        state = self.state_by_name[npc.name]

        if state.decision_ticks_until_check <= 0:
            planned = self.planner.activity_for_hour(self._current_hour())
            decision_code = self._torch_decision_code(planned, state.ticks_remaining)
            if decision_code == 1:
                if self._can_interrupt_current_action(state):
                    if state.current_action != "식사":
                        state.current_action = "식사"
                        state.current_action_display = "식사"
                        state.path = []
                    state.sleep_path_initialized = False
                    state.work_path_initialized = False
                    state.ticks_remaining = 1
            elif decision_code == 2:
                if self._can_interrupt_current_action(state):
                    if state.current_action != "취침":
                        state.current_action = "취침"
                        state.current_action_display = "취침"
                        state.path = []
                        state.sleep_path_initialized = False
                        state.work_path_initialized = False
                    state.ticks_remaining = 1
            elif decision_code == 3:
                state.sleep_path_initialized = False
                self._pick_next_work_action(npc, state)
            state.decision_ticks_until_check = self.DECISION_INTERVAL_TICKS

        state.decision_ticks_until_check = max(0, state.decision_ticks_until_check - 1)
        state.ticks_remaining = max(0, state.ticks_remaining - 1)

        width_tiles = max(1, self.world.width_px // self.world.grid_size)
        height_tiles = max(1, self.world.height_px // self.world.grid_size)
        if state.current_action == "식사" and self.dining_tiles:
            if not state.path:
                state.path = self._find_path_to_nearest_target(
                    (npc.x, npc.y),
                    self.dining_tiles,
                    width_tiles,
                    height_tiles,
                )
            if self._apply_next_path_step(npc, state):
                return

        if state.current_action == "취침" and self.bed_tiles:
            if not state.sleep_path_initialized:
                state.path = self._find_path_to_nearest_target(
                    (npc.x, npc.y),
                    self.bed_tiles,
                    width_tiles,
                    height_tiles,
                )
                state.sleep_path_initialized = True
            if self._apply_next_path_step(npc, state):
                return
            if (npc.x, npc.y) in self.bed_tiles:
                return

        if state.current_action not in {"식사", "취침"}:
            if state.current_action == "탐색":
                moved = self._step_exploration_action(npc, state, width_tiles, height_tiles)
                if moved:
                    return
                state.work_path_initialized = False

            work_tiles = self._find_work_tiles(state.current_action)
            if work_tiles:
                if not state.work_path_initialized:
                    state.path = self._find_path_to_nearest_target(
                        (npc.x, npc.y),
                        work_tiles,
                        width_tiles,
                        height_tiles,
                    )
                    state.work_path_initialized = True
                if self._apply_next_path_step(npc, state):
                    return
                if (npc.x, npc.y) in work_tiles:
                    if self._is_board_check_like_action(state.current_action):
                        self._handle_board_check(npc.name)
                    elif self._is_board_report_like_action(state.current_action):
                        self._handle_board_report(npc.name)
                    return

        self._step_random(npc, width_tiles, height_tiles)

    def _try_assign_order_after_board_check(self, npc: RenderNpc, state: SimulationNpcState) -> None:
        assigned = self.work_order_queue.assign_next(npc.job, npc.name)
        if assigned is None:
            state.contract_state = "NO_CONTRACT"
            state.contract_execute_state = "IDLE"
            state.assigned_order_id = ""
            state.current_action = "배회"
            state.current_action_display = "배회"
            state.ticks_remaining = 1
            state.path = []
            state.work_path_initialized = False
            return

        state.assigned_order_id = assigned.order_id
        state.contract_state = "EXECUTING"
        state.contract_execute_state = "RUNNING"
        action = assigned.action_name
        state.current_action = action
        state.current_action_display = self.display_action_name(
            action,
            assigned.resource_key,
            issue_type=assigned.issue_type.value,
            item_key=assigned.item_key,
        )
        state.ticks_remaining = self._work_duration_for_action(action, npc, state)
        state.path = []
        state.work_path_initialized = False

    def tick_once(self) -> None:
        self._refresh_guild_dispatcher()
        self.ticks += 1
        if self.ticks % (24 * self.TICKS_PER_HOUR) == 0:
            self._recompute_work_orders(reason="midnight")
        width_tiles = max(1, self.world.width_px // self.world.grid_size)
        height_tiles = max(1, self.world.height_px // self.world.grid_size)

        grouped_requests: Dict[Tuple[str, Tuple[Tuple[int, int], ...]], List[Tuple[RenderNpc, SimulationNpcState]]] = {}
        fallback_random: List[RenderNpc] = []

        for npc in self.npcs:
            state = self.state_by_name[npc.name]

            if state.decision_ticks_until_check <= 0:
                planned = self.planner.activity_for_hour(self._current_hour())
                decision_code = self._torch_decision_code(planned, state.ticks_remaining)
                if decision_code == 1:
                    if self._can_interrupt_current_action(state):
                        if state.current_action != "식사":
                            state.current_action = "식사"
                            state.current_action_display = "식사"
                            state.path = []
                        state.sleep_path_initialized = False
                        state.work_path_initialized = False
                        state.ticks_remaining = 1
                elif decision_code == 2:
                    if self._can_interrupt_current_action(state):
                        if state.current_action != "취침":
                            state.current_action = "취침"
                            state.current_action_display = "취침"
                            state.path = []
                            state.sleep_path_initialized = False
                            state.work_path_initialized = False
                        state.ticks_remaining = 1
                elif decision_code == 3:
                    state.sleep_path_initialized = False
                    self._pick_next_work_action(npc, state)
                state.decision_ticks_until_check = self.DECISION_INTERVAL_TICKS

            state.decision_ticks_until_check = max(0, state.decision_ticks_until_check - 1)
            state.ticks_remaining = max(0, state.ticks_remaining - 1)

            if not self._is_current_level_town():
                self._mark_visible_area_discovered(npc.name, (npc.x, npc.y))

            if state.current_action == "식사" and self.dining_tiles:
                key = ("meal", tuple(sorted(set(self.dining_tiles))))
                grouped_requests.setdefault(key, []).append((npc, state))
                continue

            if state.current_action == "취침" and self.bed_tiles:
                if not state.sleep_path_initialized:
                    state.path = self._find_path_to_nearest_target(
                        (npc.x, npc.y),
                        self.bed_tiles,
                        width_tiles,
                        height_tiles,
                    )
                    state.sleep_path_initialized = True
                key = ("sleep", tuple(sorted(set(self.bed_tiles))))
                grouped_requests.setdefault(key, []).append((npc, state))
                continue

            if state.current_action == "탐색":
                moved = self._step_exploration_action(npc, state, width_tiles, height_tiles)
                if moved:
                    continue
                state.work_path_initialized = False

            work_tiles = self._find_work_tiles(state.current_action)
            if work_tiles:
                if not state.work_path_initialized:
                    state.path = self._find_path_to_nearest_target(
                        (npc.x, npc.y),
                        work_tiles,
                        width_tiles,
                        height_tiles,
                    )
                    state.work_path_initialized = True
                key = (f"work:{state.current_action}", tuple(sorted(set(work_tiles))))
                grouped_requests.setdefault(key, []).append((npc, state))
                continue

            fallback_random.append(npc)

        for (_, target_key), rows in grouped_requests.items():
            targets = list(target_key)
            starts = [(npc.x, npc.y) for npc, _ in rows]
            next_steps = self._batch_next_steps_by_wavefront(
                starts,
                targets,
                width_tiles,
                height_tiles,
            )
            for (npc, _), step in zip(rows, next_steps):
                if step is None:
                    continue
                npc.x, npc.y = step

        for (request_key, target_key), rows in grouped_requests.items():
            action_name = request_key.removeprefix("work:")
            if not self._is_board_report_like_action(action_name):
                if not self._is_board_check_like_action(action_name):
                    continue
            targets = set(target_key)
            for npc, _ in rows:
                if (npc.x, npc.y) not in targets:
                    continue
                state = self.state_by_name[npc.name]
                if self._is_board_check_like_action(action_name):
                    self._handle_board_check(npc.name)
                    if not state.assigned_order_id:
                        self._try_assign_order_after_board_check(npc, state)
                else:
                    self._handle_board_report(npc.name)
                    self._recompute_work_orders(reason="board_report")

        for npc in self.npcs:
            state = self.state_by_name[npc.name]
            if state.assigned_order_id and state.ticks_remaining <= 0:
                self._apply_order_completion_effects(state.assigned_order_id)
                self.work_order_queue.complete(state.assigned_order_id, self.ticks)
                state.assigned_order_id = ""
                state.contract_state = "NO_CONTRACT"
                state.contract_execute_state = "IDLE"
                self._recompute_work_orders(reason="order_done")

        for npc in fallback_random:
            self._step_random(npc, width_tiles, height_tiles)

        for monster in self.monsters:
            self._step_random(monster, width_tiles, height_tiles)

    def advance(self, delta_time: float) -> None:
        self._accumulator += max(0.0, float(delta_time))
        while self._accumulator >= self.tick_seconds:
            self._accumulator -= self.tick_seconds
            self.tick_once()


def _stable_layer_color(layer_name: str) -> tuple[int, int, int, int]:
    seed = sum(ord(ch) for ch in layer_name)
    r = 40 + (seed * 37) % 120
    g = 50 + (seed * 57) % 120
    b = 60 + (seed * 79) % 120
    return int(r), int(g), int(b), 130


def _npc_color(job_name: str) -> tuple[int, int, int, int]:
    seed = sum(ord(ch) for ch in job_name)
    r = 140 + (seed * 17) % 95
    g = 120 + (seed * 29) % 110
    b = 130 + (seed * 43) % 95
    return int(r), int(g), int(b), 255


def _collect_render_entities(entities: List[GameEntity]) -> List[GameEntity]:
    return list(entities)


def _construction_state_minimap_color(state: CellConstructionState) -> tuple[int, int, int, int] | None:
    if state == CellConstructionState.IN_PROGRESS:
        return 235, 208, 74, 240
    if state == CellConstructionState.COMPLETED:
        return 98, 216, 123, 240
    if state == CellConstructionState.IN_USE:
        return 224, 92, 92, 240
    return None


def _town_bounds_tiles(world: GameWorld) -> Tuple[int, int, int, int] | None:
    for region in world.level_regions:
        if region.level_id.strip().lower() == "town":
            return region.x, region.y, region.width, region.height
    return None


FONT_CANDIDATES: tuple[str, ...] = (
    "Noto Sans CJK KR",
    "Noto Sans KR",
    "NanumGothic",
    "NanumBarunGothic",
    "NanumSquare",
    "Arial Unicode MS",
    "sans-serif",
)


def _pick_font_name() -> str:
    """설치된 폰트 후보 중 첫 번째를 선택한다."""

    try:
        import pyglet

        for name in FONT_CANDIDATES:
            if pyglet.font.have_font(name):
                return name
    except Exception:
        pass
    return FONT_CANDIDATES[0]


def _build_render_npcs(world: GameWorld) -> List[RenderNpc]:
    raw_npcs = [JsonNpc.model_validate(row) for row in load_npc_templates() if isinstance(row, dict)]
    if not raw_npcs:
        return []

    width_tiles = max(1, world.width_px // world.grid_size)
    height_tiles = max(1, world.height_px // world.grid_size)
    blocked_tiles = {tuple(row) for row in world.blocked_tiles}

    town_bounds = _town_bounds_tiles(world)
    if town_bounds is None:
        spawn_x0, spawn_y0, spawn_w, spawn_h = 0, 0, width_tiles, height_tiles
    else:
        spawn_x0, spawn_y0, spawn_w, spawn_h = town_bounds

    spawn_candidates = [
        (x, y)
        for y in range(spawn_y0, spawn_y0 + max(1, spawn_h))
        for x in range(spawn_x0, spawn_x0 + max(1, spawn_w))
        if 0 <= x < width_tiles and 0 <= y < height_tiles and (x, y) not in blocked_tiles
    ]
    fallback_candidates = [
        (x, y)
        for y in range(height_tiles)
        for x in range(width_tiles)
        if (x, y) not in blocked_tiles
    ]
    if not spawn_candidates:
        spawn_candidates = fallback_candidates

    rng = Random(42)
    remaining_candidates = list(spawn_candidates)
    npc_stats_by_name: Dict[str, NpcStatEntity] = {}
    npc_stats_by_tile: Dict[Tuple[int, int], NpcStatEntity] = {}
    for entity in world.entities:
        if not isinstance(entity, NpcStatEntity):
            continue
        npc_stats_by_tile[(entity.x, entity.y)] = entity
        entity_name_key = entity.name.strip().lower()
        if entity_name_key:
            npc_stats_by_name[entity_name_key] = entity

    out: List[RenderNpc] = []
    for npc in raw_npcs:
        if npc.x is None or npc.y is None:
            if remaining_candidates:
                default_x, default_y = remaining_candidates.pop(rng.randrange(len(remaining_candidates)))
            elif spawn_candidates:
                default_x, default_y = rng.choice(spawn_candidates)
            elif fallback_candidates:
                default_x, default_y = rng.choice(fallback_candidates)
            else:
                default_x, default_y = 0, 0
        else:
            default_x, default_y = npc.x, npc.y
        x = npc.x if npc.x is not None else default_x
        y = npc.y if npc.y is not None else default_y
        x = min(max(0, int(x)), width_tiles - 1)
        y = min(max(0, int(y)), height_tiles - 1)
        ldtk_stat = npc_stats_by_name.get(npc.name.strip().lower())
        if ldtk_stat is None:
            ldtk_stat = npc_stats_by_tile.get((x, y))

        hp = int(npc.hp if npc.hp is not None else (ldtk_stat.hp if ldtk_stat else 10))
        strength = int(npc.strength if npc.strength is not None else (ldtk_stat.strength if ldtk_stat else 1))
        agility = int(npc.agility if npc.agility is not None else (ldtk_stat.agility if ldtk_stat else 1))
        focus = int(npc.focus if npc.focus is not None else (ldtk_stat.focus if ldtk_stat else 1))

        out.append(
            RenderNpc(
                name=npc.name,
                job=npc.job,
                x=x,
                y=y,
                hp=max(1, hp),
                strength=max(0, strength),
                agility=max(0, agility),
                focus=max(0, focus),
            )
        )
    return out


def _build_render_monsters(world: GameWorld) -> List[RenderNpc]:
    raw_monsters = [JsonNpc.model_validate(row) for row in load_monster_templates() if isinstance(row, dict)]
    if not raw_monsters:
        return []

    width_tiles = max(1, world.width_px // world.grid_size)
    height_tiles = max(1, world.height_px // world.grid_size)
    blocked_tiles = {tuple(row) for row in world.blocked_tiles}

    spawn_candidates = [
        (x, y)
        for y in range(height_tiles)
        for x in range(width_tiles)
        if (x, y) not in blocked_tiles
    ]
    if not spawn_candidates:
        spawn_candidates = [(0, 0)]

    rng = Random(4242)
    remaining_candidates = list(spawn_candidates)
    npc_stats_by_name: Dict[str, NpcStatEntity] = {}
    npc_stats_by_tile: Dict[Tuple[int, int], NpcStatEntity] = {}
    for entity in world.entities:
        if not isinstance(entity, NpcStatEntity):
            continue
        npc_stats_by_tile[(entity.x, entity.y)] = entity
        entity_name_key = entity.name.strip().lower()
        if entity_name_key:
            npc_stats_by_name[entity_name_key] = entity

    out: List[RenderNpc] = []
    for monster in raw_monsters:
        if monster.x is None or monster.y is None:
            if remaining_candidates:
                default_x, default_y = remaining_candidates.pop(rng.randrange(len(remaining_candidates)))
            else:
                default_x, default_y = rng.choice(spawn_candidates)
        else:
            default_x, default_y = monster.x, monster.y

        x = monster.x if monster.x is not None else default_x
        y = monster.y if monster.y is not None else default_y
        x = min(max(0, int(x)), width_tiles - 1)
        y = min(max(0, int(y)), height_tiles - 1)

        ldtk_stat = npc_stats_by_name.get(monster.name.strip().lower())
        if ldtk_stat is None:
            ldtk_stat = npc_stats_by_tile.get((x, y))

        hp = int(monster.hp if monster.hp is not None else (ldtk_stat.hp if ldtk_stat else 10))
        strength = int(monster.strength if monster.strength is not None else (ldtk_stat.strength if ldtk_stat else 1))
        agility = int(monster.agility if monster.agility is not None else (ldtk_stat.agility if ldtk_stat else 1))
        focus = int(monster.focus if monster.focus is not None else (ldtk_stat.focus if ldtk_stat else 1))

        out.append(
            RenderNpc(
                name=monster.name,
                job=monster.job,
                x=x,
                y=y,
                hp=max(1, hp),
                strength=max(0, strength),
                agility=max(0, agility),
                focus=max(0, focus),
            )
        )
    return out


def run_arcade(world: GameWorld, config: RuntimeConfig) -> None:
    import arcade

    npcs = _build_render_npcs(world)
    monsters = _build_render_monsters(world)
    simulation = SimulationRuntime(world, npcs, monsters, use_torch_for_npc=config.use_torch_for_npc)
    selected_font = _pick_font_name()
    render_entities = _collect_render_entities(world.entities)

    class VillageArcadeWindow(arcade.Window):
        def __init__(self):
            super().__init__(config.window_width, config.window_height, config.title, resizable=True)
            self.camera = arcade.Camera2D(position=(0, 0), zoom=1.0)
            self.state = CameraState(x=world.width_px / 2, y=world.height_px / 2, zoom=1.0)
            self.camera.position = (self.state.x, self.state.y)
            self.draw_interval_seconds = 0.1
            self._draw_acc = 0.0
            self._should_render = True
            self._keys: dict[int, bool] = {}
            self.selected_entity: GameEntity | None = None
            self.selected_npc: RenderNpc | None = None
            self.last_click_world: tuple[float, float] | None = None
            self.show_board_modal = False
            self.show_item_modal = False
            self.show_npc_modal = False
            self.board_modal_tab = "issues"
            self._sync_camera_after_viewport_change()

        def _sync_camera_after_viewport_change(self) -> None:
            # Arcade Camera2D의 viewport/projection을 현재 창 크기에 맞춘다.
            # resize/fullscreen 이후 이 값이 갱신되지 않으면 렌더/클릭 좌표가 어긋날 수 있다.
            self.camera.match_window(viewport=True, projection=True, scissor=True)

            half_w = (self.width / max(1e-6, self.state.zoom)) / 2.0
            half_h = (self.height / max(1e-6, self.state.zoom)) / 2.0

            world_w = float(world.width_px)
            world_h = float(world.height_px)
            visible_w = half_w * 2.0
            visible_h = half_h * 2.0

            if visible_w >= world_w:
                # 화면이 월드보다 넓으면 경계 클램프 대신 월드 중심 고정
                self.state.x = world_w / 2.0
            else:
                min_x = half_w
                max_x = world_w - half_w
                self.state.x = min(max(self.state.x, min_x), max_x)

            if visible_h >= world_h:
                # 화면이 월드보다 높으면 경계 클램프 대신 월드 중심 고정
                self.state.y = world_h / 2.0
            else:
                min_y = half_h
                max_y = world_h - half_h
                self.state.y = min(max(self.state.y, min_y), max_y)

            self.camera.position = (self.state.x, self.state.y)
            self.camera.zoom = self.state.zoom

        def on_resize(self, width: int, height: int):
            super().on_resize(width, height)
            self._sync_camera_after_viewport_change()

        @staticmethod
        def _entity_color(entity: GameEntity) -> tuple[int, int, int, int]:
            if isinstance(entity, ResourceEntity):
                return 92, 176, 112, 255
            if _has_workbench_trait(entity):
                return 198, 140, 80, 255
            return 112, 120, 156, 255

        @staticmethod
        def _tile_bottom_left_y(grid_y: int) -> float:
            return world.height_px - ((grid_y + 1) * world.grid_size)

        @staticmethod
        def _tile_center_y(grid_y: int) -> float:
            return world.height_px - (grid_y * world.grid_size + world.grid_size / 2)

        def on_update(self, delta_time: float):
            self._draw_acc += delta_time
            if self._draw_acc >= self.draw_interval_seconds:
                self._draw_acc = 0.0
                self._should_render = True

            dx = dy = 0.0
            if self._keys.get(arcade.key.A) or self._keys.get(arcade.key.LEFT):
                dx -= 1.0
            if self._keys.get(arcade.key.D) or self._keys.get(arcade.key.RIGHT):
                dx += 1.0
            if self._keys.get(arcade.key.W) or self._keys.get(arcade.key.UP):
                dy += 1.0
            if self._keys.get(arcade.key.S) or self._keys.get(arcade.key.DOWN):
                dy -= 1.0
            if dx != 0 or dy != 0:
                magnitude = (dx * dx + dy * dy) ** 0.5
                self.state.x += (dx / magnitude) * config.camera_speed * delta_time
                self.state.y += (dy / magnitude) * config.camera_speed * delta_time
                self._sync_camera_after_viewport_change()
            simulation.advance(delta_time)

        def on_key_press(self, key: int, modifiers: int):
            self._keys[key] = True
            if key == arcade.key.Q:
                self.state.zoom = max(config.zoom_min, self.state.zoom * config.zoom_out_step)
                self._sync_camera_after_viewport_change()
            elif key == arcade.key.E:
                self.state.zoom = min(config.zoom_max, self.state.zoom * config.zoom_in_step)
                self._sync_camera_after_viewport_change()
            elif key == arcade.key.F11:
                self.set_fullscreen(not self.fullscreen)
                self._sync_camera_after_viewport_change()
            elif key == arcade.key.I:
                if self.selected_entity is not None and _is_guild_board_entity(self.selected_entity):
                    self.show_board_modal = not self.show_board_modal
                    if self.show_board_modal:
                        self.show_item_modal = False
                        self.show_npc_modal = False
                elif self.selected_npc is not None:
                    self.show_npc_modal = not self.show_npc_modal
                    if self.show_npc_modal:
                        self.show_item_modal = False
                        self.show_board_modal = False
                elif self.selected_entity is None:
                    self.show_item_modal = not self.show_item_modal
                    if self.show_item_modal:
                        self.show_board_modal = False
                        self.show_npc_modal = False
            elif key == arcade.key.TAB and self.show_board_modal:
                order = ["issues", "minimap", "known_resources", "construction"]
                try:
                    idx = order.index(self.board_modal_tab)
                except ValueError:
                    idx = 0
                self.board_modal_tab = order[(idx + 1) % len(order)]
            elif key == arcade.key.J and self.show_board_modal and self.board_modal_tab == "issues":
                jobs = simulation.board_issue_filter_jobs()
                try:
                    idx = jobs.index(simulation.board_issue_job_filter)
                except ValueError:
                    idx = 0
                simulation.board_issue_job_filter = jobs[(idx + 1) % len(jobs)]

        def _screen_to_world(self, x: float, y: float) -> tuple[float, float]:
            # resize/fullscreen 이후 클릭 오프셋을 피하기 위해
            # 카메라 변환(unproject)을 우선 사용한다.
            try:
                wx, wy = self.camera.unproject((x, y))
                return float(wx), float(wy)
            except Exception:
                zoom = max(1e-6, float(self.state.zoom))
                world_x = ((float(x) - (self.width / 2.0)) / zoom) + float(self.state.x)
                world_y = ((float(y) - (self.height / 2.0)) / zoom) + float(self.state.y)
                return world_x, world_y

        def _screen_to_world_via_unproject(self, x: float, y: float) -> tuple[float, float]:
            try:
                wx, wy = self.camera.unproject((x, y))
                return float(wx), float(wy)
            except Exception:
                return float(x), float(y)

        def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
            if button != arcade.MOUSE_BUTTON_LEFT:
                return
            world_x, world_y = self._screen_to_world(x, y)
            self.last_click_world = (world_x, world_y)
            selected = _pick_entity_near_world_point(
                render_entities,
                world_x,
                world_y,
                tile_size=world.grid_size,
                world_height_px=world.height_px,
            )
            selected_npc = _pick_npc_near_world_point(
                npcs,
                world_x,
                world_y,
                tile_size=world.grid_size,
                world_height_px=world.height_px,
            )
            self.selected_entity = selected
            self.selected_npc = selected_npc
            if selected is None or not _is_guild_board_entity(selected):
                self.show_board_modal = False
                self.board_modal_tab = "issues"
            if selected is not None or selected_npc is not None:
                self.show_item_modal = False
            if selected_npc is None:
                self.show_npc_modal = False

        def on_key_release(self, key: int, modifiers: int):
            self._keys[key] = False

        def on_draw(self):
            if not self._should_render:
                return
            self._should_render = False

            self.clear((25, 28, 32, 255))
            tile = world.grid_size
            with self.camera.activate():
                arcade.draw_lrbt_rectangle_filled(0, world.width_px, 0, world.height_px, (38, 42, 50, 255))

                for tile_row in world.tiles:
                    tx = tile_row.x * tile
                    ty = self._tile_bottom_left_y(tile_row.y)
                    arcade.draw_lrbt_rectangle_filled(
                        tx,
                        tx + tile,
                        ty,
                        ty + tile,
                        _stable_layer_color(tile_row.layer),
                    )

                for y in range(0, world.height_px, tile):
                    arcade.draw_line(0, y, world.width_px, y, (46, 52, 60, 80), 1)
                for x in range(0, world.width_px, tile):
                    arcade.draw_line(x, 0, x, world.height_px, (46, 52, 60, 80), 1)

                for npc in npcs:
                    nx = npc.x * tile + tile / 2
                    ny = self._tile_center_y(npc.y)
                    arcade.draw_circle_filled(nx, ny, max(4, tile * 0.24), _npc_color(npc.job))
                    if self.selected_npc is npc:
                        arcade.draw_circle_outline(nx, ny, max(6, tile * 0.42), (255, 215, 0, 255), 2)
                    sim_state = simulation.state_by_name.get(npc.name)
                    label = npc.name if sim_state is None else f"{npc.name}({sim_state.current_action_display})"
                    arcade.draw_text(label, nx + 5, ny - 12, (240, 240, 240, 255), 9, font_name=selected_font)

                for monster in monsters:
                    mx = monster.x * tile + tile / 2
                    my = self._tile_center_y(monster.y)
                    arcade.draw_circle_filled(mx, my, max(4, tile * 0.22), (235, 92, 92, 255))
                    arcade.draw_text(monster.name, mx + 5, my - 12, (245, 188, 188, 255), 9, font_name=selected_font)

                for entity in render_entities:
                    ex = entity.x * tile + tile / 2
                    ey = self._tile_center_y(entity.y)
                    arcade.draw_circle_filled(ex, ey, max(4, tile * 0.28), self._entity_color(entity))
                    arcade.draw_text(entity.name, ex + 6, ey + 6, (230, 230, 230, 255), 10, font_name=selected_font)
                    if self.selected_entity is entity:
                        arcade.draw_circle_outline(ex, ey, max(6, tile * 0.42), (255, 215, 0, 255), 2)

                if self.last_click_world is not None:
                    cx, cy = self.last_click_world
                    half = max(4.0, tile * 0.16)
                    arcade.draw_line(cx - half, cy, cx + half, cy, (255, 238, 88, 220), 2)
                    arcade.draw_line(cx, cy - half, cx, cy + half, (255, 238, 88, 220), 2)

            if self.selected_npc is not None:
                selected_name = f"NPC:{self.selected_npc.name}"
            elif self.selected_entity is not None:
                selected_name = self.selected_entity.name
            else:
                selected_name = "없음"
            hud = (
                f"WASD/Arrow: move | Q/E: zoom | F11: fullscreen | Click: 선택 | I: 게시판/NPC/아이템 모달 | "
                f"선택:{selected_name} | {simulation.display_clock_by_interval(30)}"
            )
            arcade.draw_text(hud, 12, self.height - 24, (220, 220, 220, 255), 12, font_name=selected_font)

            if self.show_item_modal:
                modal_w = max(260.0, self.width / 3.0)
                modal_h = float(self.height)
                left = self.width - modal_w
                bottom = 0.0
                arcade.draw_lrbt_rectangle_filled(0, self.width, 0, self.height, (0, 0, 0, 110))
                arcade.draw_lrbt_rectangle_filled(left, left + modal_w, bottom, bottom + modal_h, (28, 32, 40, 245))
                arcade.draw_lrbt_rectangle_outline(left, left + modal_w, bottom, bottom + modal_h, (220, 220, 220, 255), 2)
                arcade.draw_text("아이템 목록", left + 16, bottom + modal_h - 34, (245, 245, 245, 255), 16, font_name=selected_font)
                arcade.draw_text("(I 키로 닫기)", left + modal_w - 120, bottom + modal_h - 30, (200, 200, 200, 255), 10, font_name=selected_font)
                lines = _format_item_catalog_lines()
                for idx, line in enumerate(lines[:28]):
                    arcade.draw_text(
                        line,
                        left + 18,
                        bottom + modal_h - 84 - (idx * 22),
                        (230, 230, 230, 255),
                        11,
                        font_name=selected_font,
                    )

            if self.show_npc_modal and self.selected_npc is not None:
                modal_w = max(260.0, self.width / 3.0)
                modal_h = float(self.height)
                left = self.width - modal_w
                bottom = 0.0
                arcade.draw_lrbt_rectangle_filled(0, self.width, 0, self.height, (0, 0, 0, 110))
                arcade.draw_lrbt_rectangle_filled(left, left + modal_w, bottom, bottom + modal_h, (28, 32, 40, 245))
                arcade.draw_lrbt_rectangle_outline(left, left + modal_w, bottom, bottom + modal_h, (220, 220, 220, 255), 2)
                arcade.draw_text("NPC 정보", left + 16, bottom + modal_h - 34, (245, 245, 245, 255), 16, font_name=selected_font)
                arcade.draw_text("(I 키로 닫기)", left + modal_w - 120, bottom + modal_h - 30, (200, 200, 200, 255), 10, font_name=selected_font)
                lines = [
                    f"name: {self.selected_npc.name}",
                    f"job: {self.selected_npc.job}",
                    f"x: {int(self.selected_npc.x)}",
                    f"y: {int(self.selected_npc.y)}",
                    f"hp: {int(self.selected_npc.hp)}",
                    f"strength: {int(self.selected_npc.strength)}",
                    f"agility: {int(self.selected_npc.agility)}",
                    f"focus: {int(self.selected_npc.focus)}",
                ]
                for idx, line in enumerate(lines):
                    arcade.draw_text(
                        line,
                        left + 18,
                        bottom + modal_h - 84 - (idx * 24),
                        (230, 230, 230, 255),
                        12,
                        font_name=selected_font,
                    )

            if self.show_board_modal:
                # 화면을 세로 3등분했을 때, 오른쪽 1/3을 게시판 모달이 덮도록 배치
                modal_w = max(260.0, self.width / 3.0)
                modal_h = float(self.height)
                left = self.width - modal_w
                bottom = 0.0
                arcade.draw_lrbt_rectangle_filled(0, self.width, 0, self.height, (0, 0, 0, 110))
                arcade.draw_lrbt_rectangle_filled(left, left + modal_w, bottom, bottom + modal_h, (28, 32, 40, 245))
                arcade.draw_lrbt_rectangle_outline(left, left + modal_w, bottom, bottom + modal_h, (220, 220, 220, 255), 2)
                arcade.draw_text("게시판 발행 의뢰", left + 16, bottom + modal_h - 34, (245, 245, 245, 255), 16, font_name=selected_font)
                arcade.draw_text("(I 키로 닫기)", left + modal_w - 120, bottom + modal_h - 30, (200, 200, 200, 255), 10, font_name=selected_font)
                tab_name_map = {
                    "issues": "의뢰 목록",
                    "minimap": "미니맵",
                    "known_resources": "길드 인벤토리",
                    "construction": "건설",
                }
                tab_name = tab_name_map.get(self.board_modal_tab, "의뢰 목록")
                arcade.draw_text(
                    f"탭: {tab_name} (TAB 전환)",
                    left + 18,
                    bottom + modal_h - 54,
                    (210, 210, 210, 255),
                    11,
                    font_name=selected_font,
                )
                if self.board_modal_tab == "issues":
                    arcade.draw_text(
                        f"직업 필터: {simulation.board_issue_job_filter} (J 전환)",
                        left + 18,
                        bottom + modal_h - 72,
                        (210, 210, 210, 255),
                        11,
                        font_name=selected_font,
                    )

                if self.board_modal_tab == "issues":
                    lines = _format_guild_issue_lines(simulation)
                    for idx, line in enumerate(lines[:9]):
                        arcade.draw_text(
                            line,
                            left + 18,
                            bottom + modal_h - 104 - (idx * 24),
                            (230, 230, 230, 255),
                            12,
                            font_name=selected_font,
                        )
                elif self.board_modal_tab == "known_resources":
                    known_available = simulation._known_available_by_key_from_board()
                    keys = sorted(set(simulation.guild_inventory_by_key.keys()) | set(simulation.target_stock_by_key.keys()))
                    arcade.draw_text(
                        "name | inv | target | deficit | known",
                        left + 18,
                        bottom + modal_h - 84,
                        (210, 210, 210, 255),
                        11,
                        font_name=selected_font,
                    )
                    if not keys:
                        arcade.draw_text(
                            "재고/목표 데이터 없음",
                            left + 18,
                            bottom + modal_h - 106,
                            (205, 205, 205, 255),
                            11,
                            font_name=selected_font,
                        )
                    else:
                        for idx, key in enumerate(keys[:14]):
                            name = simulation.display_item_name(key)
                            inv = max(0, int(simulation.guild_inventory_by_key.get(key, 0)))
                            target = max(0, int(simulation.target_stock_by_key.get(key, 0)))
                            deficit = max(0, target - inv)
                            known = max(0, int(known_available.get(key, 0)))
                            arcade.draw_text(
                                f"{name:<10} | {inv:>3} | {target:>3} | {deficit:>3} | {known:>3}",
                                left + 18,
                                bottom + modal_h - 106 - (idx * 22),
                                (230, 230, 230, 255),
                                11,
                                font_name=selected_font,
                            )
                elif self.board_modal_tab == "construction":
                    mini_left = left + 18
                    mini_bottom = bottom + 48
                    mini_w = modal_w - 36
                    mini_h = modal_h - 152
                    arcade.draw_lrbt_rectangle_filled(
                        mini_left,
                        mini_left + mini_w,
                        mini_bottom,
                        mini_bottom + mini_h,
                        (18, 20, 26, 255),
                    )

                    width_tiles = max(1, world.width_px // world.grid_size)
                    height_tiles = max(1, world.height_px // world.grid_size)
                    cell_size = min(mini_w / width_tiles, mini_h / height_tiles)
                    map_w = width_tiles * cell_size
                    map_h = height_tiles * cell_size
                    map_left = mini_left + (mini_w - map_w) / 2
                    map_bottom = mini_bottom + (mini_h - map_h) / 2

                    for cy in range(height_tiles):
                        for cx in range(width_tiles):
                            state_color = _construction_state_minimap_color(
                                simulation.get_cell_runtime_state((cx, cy))
                            )
                            if state_color is None:
                                continue
                            px = map_left + (cx * cell_size)
                            py = map_bottom + ((height_tiles - cy - 1) * cell_size)
                            arcade.draw_lrbt_rectangle_filled(px, px + cell_size, py, py + cell_size, state_color)

                    legend_left = left + 18
                    legend_y = bottom + 22
                    legend_rows = [
                        ("미개척", None),
                        ("개척중", (235, 208, 74, 240)),
                        ("개척완료", (98, 216, 123, 240)),
                        ("사용중", (224, 92, 92, 240)),
                    ]
                    cursor_x = legend_left
                    for label, color in legend_rows:
                        if color is not None:
                            arcade.draw_lrbt_rectangle_filled(cursor_x, cursor_x + 10, legend_y, legend_y + 10, color)
                            arcade.draw_lrbt_rectangle_outline(cursor_x, cursor_x + 10, legend_y, legend_y + 10, (220, 220, 220, 160), 1)
                        else:
                            arcade.draw_lrbt_rectangle_outline(cursor_x, cursor_x + 10, legend_y, legend_y + 10, (135, 135, 135, 140), 1)
                        arcade.draw_text(label, cursor_x + 14, legend_y - 2, (220, 220, 220, 255), 10, font_name=selected_font)
                        cursor_x += 82

                    arcade.draw_lrbt_rectangle_outline(
                        map_left,
                        map_left + map_w,
                        map_bottom,
                        map_bottom + map_h,
                        (220, 220, 220, 255),
                        1,
                    )
                else:
                    mini_left = left + 18
                    mini_bottom = bottom + 18
                    mini_w = modal_w - 36
                    mini_h = modal_h - 96
                    arcade.draw_lrbt_rectangle_filled(
                        mini_left,
                        mini_left + mini_w,
                        mini_bottom,
                        mini_bottom + mini_h,
                        (18, 20, 26, 255),
                    )

                    width_tiles = max(1, world.width_px // world.grid_size)
                    height_tiles = max(1, world.height_px // world.grid_size)
                    cell_size = min(mini_w / width_tiles, mini_h / height_tiles)
                    map_w = width_tiles * cell_size
                    map_h = height_tiles * cell_size
                    map_left = mini_left + (mini_w - map_w) / 2
                    map_bottom = mini_bottom + (mini_h - map_h) / 2

                    known_cells = simulation.minimap_known_cells_snapshot
                    known_resources = simulation.minimap_known_resources_snapshot
                    known_monsters = simulation.minimap_known_monsters_snapshot

                    for cx, cy in known_cells:
                        px = map_left + (cx * cell_size)
                        py = map_bottom + ((height_tiles - cy - 1) * cell_size)
                        arcade.draw_lrbt_rectangle_filled(px, px + cell_size, py, py + cell_size, (245, 245, 245, 230))

                    if not known_cells:
                        arcade.draw_text(
                            "게시판 보고 후 미니맵 갱신",
                            map_left + 10,
                            map_bottom + map_h - 24,
                            (205, 205, 205, 255),
                            10,
                            font_name=selected_font,
                        )

                    for (_name, (rx, ry)), amount in known_resources.items():
                        if (rx, ry) not in known_cells or int(amount) <= 0:
                            continue
                        px = map_left + ((rx + 0.5) * cell_size)
                        py = map_bottom + ((height_tiles - ry - 0.5) * cell_size)
                        arcade.draw_circle_filled(px, py, max(1.0, cell_size * 0.16), (100, 220, 120, 255))

                    for _monster_name, (mx, my) in known_monsters:
                        if (mx, my) not in known_cells:
                            continue
                        px = map_left + ((mx + 0.5) * cell_size)
                        py = map_bottom + ((height_tiles - my - 0.5) * cell_size)
                        half = max(1.0, cell_size * 0.12)
                        arcade.draw_lrbt_rectangle_filled(px - half, px + half, py - half, py + half, (235, 92, 92, 255))

                    for npc in npcs:
                        px = map_left + ((npc.x + 0.5) * cell_size)
                        py = map_bottom + ((height_tiles - npc.y - 0.5) * cell_size)
                        arcade.draw_circle_filled(px, py, max(1.2, cell_size * 0.2), (248, 226, 110, 255))

                    for monster in monsters:
                        px = map_left + ((monster.x + 0.5) * cell_size)
                        py = map_bottom + ((height_tiles - monster.y - 0.5) * cell_size)
                        half = max(1.0, cell_size * 0.18)
                        arcade.draw_lrbt_rectangle_filled(px - half, px + half, py - half, py + half, (235, 92, 92, 255))

                    arcade.draw_lrbt_rectangle_outline(
                        map_left,
                        map_left + map_w,
                        map_bottom,
                        map_bottom + map_h,
                        (220, 220, 220, 255),
                        1,
                    )

    VillageArcadeWindow()
    arcade.run()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Arcade village simulator runner")
    default_ldtk = DATA_DIR / "map.ldtk"
    parser.add_argument("--ldtk", default=str(default_ldtk), help=f"Path to LDtk project (default: {default_ldtk})")
    parser.add_argument("--level", default=None, help="LDtk level identifier")
    parser.add_argument("--all-levels", action="store_true", help="Merge all LDtk levels using worldX/worldY")
    parser.add_argument("--torch-npc", action="store_true", help="Use torch-backed decision/movement for NPC logic")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = RuntimeConfig(use_torch_for_npc=bool(args.torch_npc))
    world = build_world_from_ldtk(
        Path(args.ldtk),
        level_identifier=args.level,
        merge_all_levels=args.level is None,
    )
    run_arcade(world, config)


if __name__ == "__main__":
    main()
