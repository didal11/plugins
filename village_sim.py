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
    load_job_defs,
    load_npc_templates,
)
from ldtk_integration import (
    GameEntity,
    GameWorld,
    ResourceEntity,
    StructureEntity,
    WorkbenchEntity,
    build_world_from_ldtk,
)
from guild_dispatch import GuildDispatcher
from exploration import GuildBoardExplorationState, NPCExplorationBuffer, choose_next_frontier
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
    issued = simulation.guild_dispatcher.issue_for_targets(
        simulation.target_stock_by_key,
        simulation.target_available_by_key,
    )
    if not issued:
        return ["발행된 의뢰가 없습니다."]
    out: List[str] = []
    for row in issued:
        display_action = simulation.display_action_name(row.action_name, row.resource_key)
        display_resource = simulation.display_resource_name(row.resource_key)
        out.append(f"- {display_action} | 자원:{display_resource} | 수량:{int(row.amount)}")
    return out


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


class RenderNpc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    job: str
    x: int
    y: int


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


class SimulationRuntime:
    """렌더 루프와 분리된 고정 틱(1분 단위) 시뮬레이터."""

    TICK_MINUTES = 1
    TICKS_PER_HOUR = 60 // TICK_MINUTES
    DECISION_INTERVAL_TICKS = 10

    def __init__(
        self,
        world: GameWorld,
        npcs: List[RenderNpc],
        tick_seconds: float = 0.1,
        seed: int = 42,
        use_torch_for_npc: bool = False,
    ):
        self.world = world
        self.npcs = npcs
        self.tick_seconds = max(0.1, float(tick_seconds))
        self._accumulator = 0.0
        self.ticks = 0
        self.rng = Random(seed)
        self.planner = DailyPlanner()
        self.use_torch_for_npc = bool(use_torch_for_npc and torch is not None)

        self.job_actions = self._job_actions_map()
        self.action_duration_ticks = self._action_duration_map()
        self.action_required_entity = self._action_required_entity_map()
        self.guild_inventory_by_key: Dict[str, int] = {}
        self.guild_dispatcher = GuildDispatcher(self.world.entities)
        self.target_stock_by_key, self.target_available_by_key = {}, {}
        self._refresh_guild_dispatcher()
        self.state_by_name: Dict[str, SimulationNpcState] = {
            npc.name: SimulationNpcState() for npc in self.npcs
        }
        self.exploration_buffer_by_name: Dict[str, NPCExplorationBuffer] = {
            npc.name: NPCExplorationBuffer() for npc in self.npcs
        }
        self.minimap_known_cells_snapshot: Set[Tuple[int, int]] = set()
        self.blocked_tiles = {tuple(row) for row in self.world.blocked_tiles}
        self.dining_tiles = self._find_dining_tiles()
        self.bed_tiles = self._find_bed_tiles()
        self.guild_board_exploration_state = GuildBoardExplorationState()
        self._initialize_exploration_state()

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

    def _refresh_guild_dispatcher(self) -> None:
        registered_resources = self._dynamic_registered_resource_keys()
        for key in registered_resources:
            if key not in self.guild_inventory_by_key:
                self.guild_inventory_by_key[key] = 0

        self.guild_dispatcher = GuildDispatcher(
            self.world.entities,
            registered_resource_keys=registered_resources,
            stock_by_key=self.guild_inventory_by_key,
            count_available_only_discovered=True,
        )

        target_stock, target_available = self._default_guild_targets()
        self.target_stock_by_key = {
            key: int(self.target_stock_by_key.get(key, target_stock.get(key, 1)))
            for key in self.guild_dispatcher.resource_keys
        }
        self.target_available_by_key = {
            key: int(self.target_available_by_key.get(key, target_available.get(key, 1)))
            for key in self.guild_dispatcher.resource_keys
        }

    def _default_guild_targets(self) -> Tuple[Dict[str, int], Dict[str, int]]:
        target_stock_by_key = {key: 1 for key in self.guild_dispatcher.resource_keys}
        target_available_by_key = {key: 1 for key in self.guild_dispatcher.resource_keys}
        return target_stock_by_key, target_available_by_key

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

    def display_action_name(self, action_name: str, resource_key: str) -> str:
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
        for coord in self._town_walkable_cells():
            self._mark_cell_discovered(coord, force=True)
        for npc in self.npcs:
            self._mark_cell_discovered((npc.x, npc.y), force=True)

    def _grid_bounds(self) -> Tuple[int, int]:
        width_tiles = max(1, self.world.width_px // self.world.grid_size)
        height_tiles = max(1, self.world.height_px // self.world.grid_size)
        return width_tiles, height_tiles

    def _is_known_from_view(self, coord: Tuple[int, int], buffer: NPCExplorationBuffer) -> bool:
        return coord in self.guild_board_exploration_state.known_cells or coord in buffer.new_known_cells

    def _frontier_cells_from_known_view(self, buffer: NPCExplorationBuffer) -> Set[Tuple[int, int]]:
        """Compute frontier cells at runtime from known cells.

        frontier 정의: known 셀의 8방향 이웃 중 아직 known이 아닌 셀.
        """

        known_view = self.guild_board_exploration_state.known_cells.union(buffer.new_known_cells)
        width_tiles, height_tiles = self._grid_bounds()
        frontier: Set[Tuple[int, int]] = set()
        for x, y in known_view:
            for nx, ny in self._neighbors(x, y, width_tiles, height_tiles):
                nb = (nx, ny)
                if nb in self.blocked_tiles:
                    continue
                if nb in known_view:
                    continue
                frontier.add(nb)
        return frontier

    def _mark_cell_discovered_to_buffer(
        self,
        buffer: NPCExplorationBuffer,
        coord: Tuple[int, int],
        force: bool = False,
    ) -> None:
        x, y = coord
        width_tiles, height_tiles = self._grid_bounds()
        if x < 0 or y < 0 or x >= width_tiles or y >= height_tiles:
            return
        if coord in self.blocked_tiles:
            return
        if self._is_known_from_view(coord, buffer):
            return

        if not force:
            has_adjacent_known = self._has_adjacent_known_8(x, y, width_tiles, height_tiles, buffer)
            if not has_adjacent_known:
                return

        buffer.new_known_cells.add(coord)

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
        if not buffer.new_known_cells and not buffer.intel_updates:
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
        if delta.new_known_cells:
            buffer.new_known_cells.update(delta.new_known_cells)
        if delta.intel_updates:
            buffer.intel_updates.update(delta.intel_updates)

    def _handle_board_report(self, npc_name: str) -> None:
        self._flush_exploration_buffer(npc_name)
        self.minimap_known_cells_snapshot = set(self.guild_board_exploration_state.known_cells)

    def _mark_cell_discovered(self, coord: Tuple[int, int], force: bool = False) -> None:
        """Backward-compatible helper used by tests/system flows.

        실제 known/frontier 반영은 버퍼를 통해서만 수행한다.
        """

        system_name = "__system__"
        buffer = self.exploration_buffer_by_name.setdefault(system_name, NPCExplorationBuffer())
        self._mark_cell_discovered_to_buffer(buffer, coord, force=force)
        self._flush_exploration_buffer(system_name)

    def _mark_visible_area_discovered(self, npc_name: str, coord: Tuple[int, int]) -> None:
        buffer = self.exploration_buffer_by_name.setdefault(npc_name, NPCExplorationBuffer())
        x, y = coord
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                self._mark_cell_discovered_to_buffer(buffer, (x + dx, y + dy))

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

    @staticmethod
    def _entity_matches_key(entity: GameEntity, required_key: str) -> bool:
        required = required_key.strip().lower()
        key = entity.key.strip().lower()
        if not required or not key:
            return False
        return key == required or key.startswith(f"{required}_")

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
        """업무 시간에만 호출되는 업무 선택 로직."""

        candidates = self.job_actions.get(npc.job, [])
        if npc.job.strip() == "모험가":
            check_action = self._board_check_action_name_in_candidates(candidates)
            report_action = self._board_report_action_name_in_candidates(candidates)

            if not state.board_cycle_checked and check_action is not None:
                state.current_action = check_action
                state.current_action_display = check_action
                state.ticks_remaining = self.action_duration_ticks.get(check_action, 1)
                state.path = []
                state.work_path_initialized = False
                state.board_cycle_checked = True
                return

            if state.board_cycle_needs_report and report_action is not None:
                state.current_action = report_action
                state.current_action_display = report_action
                state.ticks_remaining = self.action_duration_ticks.get(report_action, 1)
                state.path = []
                state.work_path_initialized = False
                state.board_cycle_checked = False
                state.board_cycle_needs_report = False
                return

            issued = self.guild_dispatcher.issue_for_targets(
                self.target_stock_by_key,
                self.target_available_by_key,
            )
            issued_actions: List[Tuple[str, str]] = []
            allowed = set(candidates)
            for row in issued:
                if row.action_name not in allowed:
                    continue
                display_action = self.display_action_name(row.action_name, row.resource_key)
                issued_actions.extend([(row.action_name, display_action)] * max(1, int(row.amount)))
            if issued_actions:
                action, display_action = self.rng.choice(issued_actions)
                state.current_action = action
                state.current_action_display = display_action
                state.ticks_remaining = self.action_duration_ticks.get(action, 1)
                state.path = []
                state.work_path_initialized = False
                state.board_cycle_needs_report = True
                return
            state.board_cycle_checked = False
            state.board_cycle_needs_report = False
            candidates = []

        if not candidates:
            state.current_action = "배회"
            state.current_action_display = "배회"
            state.ticks_remaining = 1
            state.path = []
            return
        action = self.rng.choice(candidates)
        state.current_action = action
        state.current_action_display = action
        state.ticks_remaining = self.action_duration_ticks.get(action, 1)
        state.path = []
        state.work_path_initialized = False

    def _neighbors(self, x: int, y: int, width_tiles: int, height_tiles: int) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nx < 0 or ny < 0 or nx >= width_tiles or ny >= height_tiles:
                continue
            if (nx, ny) in self.blocked_tiles:
                continue
            out.append((nx, ny))
        return out

    @staticmethod
    def _distance_to_targets(x: int, y: int, targets: List[Tuple[int, int]]) -> int:
        return min(abs(x - tx) + abs(y - ty) for tx, ty in targets)

    def _find_path_to_nearest_target(
        self,
        start: Tuple[int, int],
        targets: List[Tuple[int, int]],
        width_tiles: int,
        height_tiles: int,
    ) -> List[Tuple[int, int]]:
        if not targets or start in targets:
            return []
        distances = self._wavefront_distances(targets, width_tiles, height_tiles)
        sx, sy = start
        if distances[sy][sx] >= 10**9:
            return []

        path: List[Tuple[int, int]] = []
        cx, cy = sx, sy
        while distances[cy][cx] > 0:
            best_next: Tuple[int, int] | None = None
            best_dist = distances[cy][cx]
            for nx, ny in self._neighbors(cx, cy, width_tiles, height_tiles):
                nb_dist = distances[ny][nx]
                if nb_dist > best_dist:
                    continue
                if nb_dist < best_dist or best_next is None or (ny, nx) < (best_next[1], best_next[0]):
                    best_dist = nb_dist
                    best_next = (nx, ny)
            if best_next is None:
                return []
            path.append(best_next)
            cx, cy = best_next
        return path

    def _wavefront_distances(
        self,
        targets: List[Tuple[int, int]],
        width_tiles: int,
        height_tiles: int,
    ) -> List[List[int]]:
        inf = 10**9
        distances = [[inf for _ in range(width_tiles)] for _ in range(height_tiles)]
        q: deque[Tuple[int, int]] = deque()

        for tx, ty in targets:
            if tx < 0 or ty < 0 or tx >= width_tiles or ty >= height_tiles:
                continue
            if (tx, ty) in self.blocked_tiles:
                continue
            if distances[ty][tx] == 0:
                continue
            distances[ty][tx] = 0
            q.append((tx, ty))

        while q:
            x, y = q.popleft()
            next_dist = distances[y][x] + 1
            for nx, ny in self._neighbors(x, y, width_tiles, height_tiles):
                if next_dist >= distances[ny][nx]:
                    continue
                distances[ny][nx] = next_dist
                q.append((nx, ny))
        return distances

    def _batch_next_steps_by_wavefront(
        self,
        starts: List[Tuple[int, int]],
        targets: List[Tuple[int, int]],
        width_tiles: int,
        height_tiles: int,
    ) -> List[Tuple[int, int] | None]:
        if not starts:
            return []

        distances = self._wavefront_distances(targets, width_tiles, height_tiles)
        out: List[Tuple[int, int] | None] = []
        for x, y in starts:
            best_next: Tuple[int, int] | None = None
            best_dist = distances[y][x] if 0 <= x < width_tiles and 0 <= y < height_tiles else 10**9
            for nx, ny in self._neighbors(x, y, width_tiles, height_tiles):
                nb_dist = distances[ny][nx]
                if nb_dist > best_dist:
                    continue
                if nb_dist < best_dist or best_next is None or (ny, nx) < (best_next[1], best_next[0]):
                    best_dist = nb_dist
                    best_next = (nx, ny)
            out.append(best_next)
        return out

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
                if state.current_action != "식사":
                    state.current_action = "식사"
                    state.current_action_display = "식사"
                    state.path = []
                state.sleep_path_initialized = False
                state.work_path_initialized = False
                state.ticks_remaining = 1
            elif decision_code == 2:
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

    def tick_once(self) -> None:
        self._refresh_guild_dispatcher()
        self.ticks += 1
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
                    if state.current_action != "식사":
                        state.current_action = "식사"
                        state.current_action_display = "식사"
                        state.path = []
                    state.sleep_path_initialized = False
                    state.work_path_initialized = False
                    state.ticks_remaining = 1
                elif decision_code == 2:
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
                if self._is_board_check_like_action(action_name):
                    self._handle_board_check(npc.name)
                else:
                    self._handle_board_report(npc.name)

        for npc in fallback_random:
            self._step_random(npc, width_tiles, height_tiles)

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
        out.append(RenderNpc(name=npc.name, job=npc.job, x=x, y=y))
    return out


def run_arcade(world: GameWorld, config: RuntimeConfig) -> None:
    import arcade

    npcs = _build_render_npcs(world)
    simulation = SimulationRuntime(world, npcs, use_torch_for_npc=config.use_torch_for_npc)
    selected_font = _pick_font_name()
    render_entities = _collect_render_entities(world.entities)

    class VillageArcadeWindow(arcade.Window):
        def __init__(self):
            super().__init__(config.window_width, config.window_height, config.title, resizable=True)
            self.camera = arcade.Camera2D(position=(0, 0), zoom=1.0)
            self.state = CameraState(x=world.width_px / 2, y=world.height_px / 2, zoom=1.0)
            self.camera.position = (self.state.x, self.state.y)
            self._keys: dict[int, bool] = {}
            self.selected_entity: GameEntity | None = None
            self.last_click_world: tuple[float, float] | None = None
            self.show_board_modal = False
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
            elif key == arcade.key.TAB and self.show_board_modal:
                self.board_modal_tab = "minimap" if self.board_modal_tab == "issues" else "issues"

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
            self.selected_entity = selected
            if selected is None or not _is_guild_board_entity(selected):
                self.show_board_modal = False
                self.board_modal_tab = "issues"

        def on_key_release(self, key: int, modifiers: int):
            self._keys[key] = False

        def on_draw(self):
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
                    sim_state = simulation.state_by_name.get(npc.name)
                    label = npc.name if sim_state is None else f"{npc.name}({sim_state.current_action_display})"
                    arcade.draw_text(label, nx + 5, ny - 12, (240, 240, 240, 255), 9, font_name=selected_font)

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

            selected_name = "없음" if self.selected_entity is None else self.selected_entity.name
            hud = (
                f"WASD/Arrow: move | Q/E: zoom | F11: fullscreen | Click: 선택 | I: 게시판 의뢰 보기 | "
                f"선택:{selected_name} | {simulation.display_clock_by_interval(30)}"
            )
            arcade.draw_text(hud, 12, self.height - 24, (220, 220, 220, 255), 12, font_name=selected_font)

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
                arcade.draw_text(
                    f"탭: {'의뢰 목록' if self.board_modal_tab == 'issues' else '미니맵'} (TAB 전환)",
                    left + 18,
                    bottom + modal_h - 54,
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
                            bottom + modal_h - 84 - (idx * 24),
                            (230, 230, 230, 255),
                            12,
                            font_name=selected_font,
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

                    for entity in render_entities:
                        if isinstance(entity, ResourceEntity) and not entity.is_discovered:
                            continue
                        if (entity.x, entity.y) not in known_cells:
                            continue
                        px = map_left + ((entity.x + 0.5) * cell_size)
                        py = map_bottom + ((height_tiles - entity.y - 0.5) * cell_size)
                        arcade.draw_circle_filled(px, py, max(1.0, cell_size * 0.16), self._entity_color(entity))

                    for npc in npcs:
                        px = map_left + ((npc.x + 0.5) * cell_size)
                        py = map_bottom + ((height_tiles - npc.y - 0.5) * cell_size)
                        arcade.draw_circle_filled(px, py, max(1.2, cell_size * 0.2), (248, 226, 110, 255))

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
