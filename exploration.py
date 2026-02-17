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
from random import Random
from typing import Dict, Iterable, Optional, Set, Tuple


Coord = Tuple[int, int]
ResourceKey = Tuple[str, Coord]
MonsterSighting = Tuple[str, Coord]


@dataclass
class NPCExplorationBuffer:
    """NPC가 들고 다니는 탐색 증분."""

    new_known_cells: Set[Coord] = field(default_factory=set)
    known_resource_updates: Dict[ResourceKey, int] = field(default_factory=dict)
    known_resource_removals: Set[ResourceKey] = field(default_factory=set)
    known_monster_discoveries: Set[MonsterSighting] = field(default_factory=set)

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
