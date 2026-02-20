#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exploration state shared between guild board and NPC buffers.

설계 목표:
- 길드보드는 전역 상태(authoritative)
- NPC는 전체 복사본이 아닌 증분 버퍼(delta)만 보유
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import IntEnum
from random import Random
from typing import Dict, Iterable, Optional, Set, Tuple


Coord = Tuple[int, int]
ResourceKey = Tuple[str, Coord]
MonsterSighting = Tuple[str, Coord]


class CellConstructionState(IntEnum):
    UNEXPLORED = 0
    IN_PROGRESS = 1
    COMPLETED = 2
    IN_USE = 3


@dataclass
class RuntimeCellStateStore:
    """Runtime-only cell state storage with sparse change tracking.

    - baseline_completed_cells: 로드 시 기본 완료 상태(예: town)
    - overrides: baseline에서 달라진 셀만 저장
    - pending_changes: 마지막 저장 이후 변경된 좌표만 추적
    """

    baseline_completed_cells: Set[Coord] = field(default_factory=set)
    overrides: Dict[Coord, CellConstructionState] = field(default_factory=dict)
    pending_changes: Set[Coord] = field(default_factory=set)

    def get_state(self, coord: Coord) -> CellConstructionState:
        state = self.overrides.get(coord)
        if state is not None:
            return state
        if coord in self.baseline_completed_cells:
            return CellConstructionState.COMPLETED
        return CellConstructionState.UNEXPLORED

    def set_state(self, coord: Coord, state: CellConstructionState) -> bool:
        """Set runtime state. Return True when actual change occurred."""

        prev = self.get_state(coord)
        next_state = CellConstructionState(int(state))
        if prev == next_state:
            return False

        baseline = (
            CellConstructionState.COMPLETED
            if coord in self.baseline_completed_cells
            else CellConstructionState.UNEXPLORED
        )
        if next_state == baseline:
            self.overrides.pop(coord, None)
        else:
            self.overrides[coord] = next_state
        self.pending_changes.add(coord)
        return True

    def mark_baseline_completed(self, coords: Iterable[Coord]) -> None:
        """Initialize baseline completion without producing pending changes."""

        for coord in coords:
            self.baseline_completed_cells.add(coord)
            if self.overrides.get(coord) == CellConstructionState.COMPLETED:
                self.overrides.pop(coord, None)

    def pop_pending_changes(self) -> Dict[Coord, CellConstructionState]:
        """Return and clear only changed cells since last pop."""

        if not self.pending_changes:
            return {}
        out = {coord: self.get_state(coord) for coord in self.pending_changes}
        self.pending_changes.clear()
        return out


@dataclass
class NPCExplorationBuffer:
    """NPC가 들고 다니는 탐색 증분."""

    new_known_cells: Set[Coord] = field(default_factory=set)
    known_resource_updates: Dict[ResourceKey, int] = field(default_factory=dict)
    known_resource_removals: Set[ResourceKey] = field(default_factory=set)
    known_monster_discoveries: Set[MonsterSighting] = field(default_factory=set)

    def has_any_delta(self) -> bool:
        return bool(
            self.new_known_cells
            or self.known_resource_updates
            or self.known_resource_removals
            or self.known_monster_discoveries
        )

    def clear(self) -> None:
        self.new_known_cells.clear()
        self.known_resource_updates.clear()
        self.known_resource_removals.clear()
        self.known_monster_discoveries.clear()

    def record_resource_observation(
        self,
        name: str,
        coord: Coord,
        amount: int,
        global_known_resources: Dict[ResourceKey, int],
    ) -> None:
        """Record resource update delta when quantity changed or newly found."""

        key = (name, coord)
        if global_known_resources.get(key) == amount:
            return
        self.known_resource_updates[key] = amount
        self.known_resource_removals.discard(key)

    def record_resource_absence(
        self,
        name: str,
        coord: Coord,
        global_known_resources: Dict[ResourceKey, int],
    ) -> None:
        """Record resource removal delta only when resource was previously known."""

        key = (name, coord)
        if key not in global_known_resources:
            return
        self.known_resource_updates.pop(key, None)
        self.known_resource_removals.add(key)

    def record_monster_discovery(self, name: str, coord: Coord) -> None:
        """Monsters are append-only discoveries."""

        self.known_monster_discoveries.add((name, coord))

    def merge_from(self, other: "NPCExplorationBuffer") -> None:
        """Merge another delta buffer into this one."""

        if other.new_known_cells:
            self.new_known_cells.update(other.new_known_cells)
        if other.known_resource_updates:
            self.known_resource_updates.update(other.known_resource_updates)
        if other.known_resource_removals:
            self.known_resource_removals.update(other.known_resource_removals)
        if other.known_monster_discoveries:
            self.known_monster_discoveries.update(other.known_monster_discoveries)


@dataclass
class GuildBoardExplorationState:
    known_cells: Set[Coord] = field(default_factory=set)
    known_resources: Dict[ResourceKey, int] = field(default_factory=dict)
    known_monsters: Set[MonsterSighting] = field(default_factory=set)

    @classmethod
    def with_all_cells_known(cls, width: int, height: int) -> "GuildBoardExplorationState":
        """Create initial board state where every cell is already known.

        town 레벨 초기화 시 사용한다.
        """

        safe_w = max(0, int(width))
        safe_h = max(0, int(height))
        known = {(x, y) for x in range(safe_w) for y in range(safe_h)}
        return cls(known_cells=known)

    def apply_npc_buffer(self, buffer: NPCExplorationBuffer, rng: Optional[Random] = None) -> None:
        """Apply only delta updates from a NPC buffer.

        - known_cells는 set union
        - known_resources는 변경분만 반영(update/remove)
        - known_monsters는 발견분 누적(add-only)
        """

        del rng  # backward-compatible signature

        if buffer.new_known_cells:
            self.known_cells.update(buffer.new_known_cells)

        for key in buffer.known_resource_removals:
            self.known_resources.pop(key, None)

        if buffer.known_resource_updates:
            self.known_resources.update(buffer.known_resource_updates)

        if buffer.known_monster_discoveries:
            self.known_monsters.update(buffer.known_monster_discoveries)

    def export_delta_for_known_cells(self, known_cells: Iterable[Coord]) -> NPCExplorationBuffer:
        """Return only data for cells requested by NPC.

        전체 스냅샷 대신 특정 셀들에 대한 최소 데이터만 제공.
        """

        cells = set(known_cells)
        known_resource_updates = {
            key: amount
            for key, amount in self.known_resources.items()
            if key[1] in cells
        }
        known_monster_discoveries = {
            sighting
            for sighting in self.known_monsters
            if sighting[1] in cells
        }

        return NPCExplorationBuffer(
            new_known_cells=self.known_cells.intersection(cells),
            known_resource_updates=known_resource_updates,
            known_monster_discoveries=known_monster_discoveries,
        )


def choose_next_frontier(frontier_cells: Iterable[Coord], rng: Random) -> Optional[Coord]:
    """Pick next frontier randomly for realism-oriented exploration."""

    cells = list(frontier_cells)
    if not cells:
        return None
    return rng.choice(cells)


def is_known_from_view(coord: Coord, global_known_cells: Set[Coord], buffer: NPCExplorationBuffer) -> bool:
    """Return True if coord is known globally or in local NPC buffer view."""

    return coord in global_known_cells or coord in buffer.new_known_cells


def frontier_cells_from_known_view(
    buffer: NPCExplorationBuffer,
    blocked_tiles: Set[Coord],
    width_tiles: int,
    height_tiles: int,
) -> Set[Coord]:
    """Compute frontier cells from buffer-known cells only."""

    known_view = set(buffer.new_known_cells)
    frontier: Set[Coord] = set()
    for x, y in known_view:
        for ny in range(y - 1, y + 2):
            for nx in range(x - 1, x + 2):
                if nx == x and ny == y:
                    continue
                if nx < 0 or ny < 0 or nx >= width_tiles or ny >= height_tiles:
                    continue
                nb = (nx, ny)
                if nb in blocked_tiles or nb in known_view:
                    continue
                frontier.add(nb)
    return frontier


def record_known_cell_discovery(
    buffer: NPCExplorationBuffer,
    coord: Coord,
    global_known_cells: Set[Coord],
    blocked_tiles: Set[Coord],
    width_tiles: int,
    height_tiles: int,
    *,
    force: bool = False,
) -> None:
    """Record known cell into NPC buffer if discoverable."""

    x, y = coord
    if x < 0 or y < 0 or x >= width_tiles or y >= height_tiles:
        return
    if coord in blocked_tiles:
        return
    if is_known_from_view(coord, global_known_cells, buffer):
        return

    if not force:
        has_adjacent_known = False
        for ny in range(y - 1, y + 2):
            for nx in range(x - 1, x + 2):
                if nx == x and ny == y:
                    continue
                if nx < 0 or ny < 0 or nx >= width_tiles or ny >= height_tiles:
                    continue
                if is_known_from_view((nx, ny), global_known_cells, buffer):
                    has_adjacent_known = True
                    break
            if has_adjacent_known:
                break
        if not has_adjacent_known:
            return

    buffer.new_known_cells.add(coord)
