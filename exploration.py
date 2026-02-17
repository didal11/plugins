#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exploration state shared between guild board and NPC buffers.

설계 목표:
- 길드보드는 전역 상태(authoritative)
- NPC는 전체 복사본이 아닌 증분 버퍼(delta)만 보유
- 충돌은 정책 보강 없이 랜덤 선택
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from random import Random
from typing import Dict, Iterable, Optional, Set, Tuple


Coord = Tuple[int, int]


@dataclass
class IntelRecord:
    """A single intel record for a cell.

    `payload`는 리소스/몬스터 상세(JSON 유사 dict)이며
    충돌 시 랜덤 선택만 수행한다.
    """

    payload: Dict[str, object] = field(default_factory=dict)
    updated_at: int = 0
    discovered_by: str = ""


@dataclass
class CellIntel:
    resources: Optional[IntelRecord] = None
    monsters: Optional[IntelRecord] = None


@dataclass
class NPCExplorationBuffer:
    """NPC가 들고 다니는 탐색 증분."""

    new_known_cells: Set[Coord] = field(default_factory=set)
    new_frontier_cells: Set[Coord] = field(default_factory=set)
    intel_updates: Dict[Coord, CellIntel] = field(default_factory=dict)

    def clear(self) -> None:
        self.new_known_cells.clear()
        self.new_frontier_cells.clear()
        self.intel_updates.clear()


@dataclass
class GuildBoardExplorationState:
    known_cells: Set[Coord] = field(default_factory=set)
    frontier_cells: Set[Coord] = field(default_factory=set)
    cell_intel: Dict[Coord, CellIntel] = field(default_factory=dict)

    @classmethod
    def with_all_cells_known(cls, width: int, height: int) -> "GuildBoardExplorationState":
        """Create initial board state where every cell is already known.

        town 레벨 초기화 시 사용한다.
        """

        safe_w = max(0, int(width))
        safe_h = max(0, int(height))
        known = {(x, y) for x in range(safe_w) for y in range(safe_h)}
        return cls(known_cells=known)

    def apply_npc_buffer(self, buffer: NPCExplorationBuffer, rng: Random) -> None:
        """Apply only delta updates from a NPC buffer.

        - known/frontier는 set union
        - intel 충돌은 랜덤 선택
        """

        if buffer.new_known_cells:
            self.known_cells.update(buffer.new_known_cells)
        if buffer.new_frontier_cells:
            self.frontier_cells.update(buffer.new_frontier_cells)

        for coord, incoming in buffer.intel_updates.items():
            existing = self.cell_intel.get(coord)
            self.cell_intel[coord] = _merge_cell_intel(existing, incoming, rng)

    def export_delta_for_known_cells(self, known_cells: Iterable[Coord]) -> NPCExplorationBuffer:
        """Return only data for cells requested by NPC.

        전체 스냅샷 대신 특정 셀들에 대한 최소 데이터만 제공.
        """

        cells = set(known_cells)
        intel_updates = {
            c: self.cell_intel[c]
            for c in cells
            if c in self.cell_intel
        }
        return NPCExplorationBuffer(
            new_known_cells=self.known_cells.intersection(cells),
            new_frontier_cells=self.frontier_cells.intersection(cells),
            intel_updates=intel_updates,
        )


def choose_next_frontier(frontier_cells: Iterable[Coord], rng: Random) -> Optional[Coord]:
    """Pick next frontier randomly for realism-oriented exploration."""

    cells = list(frontier_cells)
    if not cells:
        return None
    return rng.choice(cells)


def _merge_cell_intel(existing: Optional[CellIntel], incoming: CellIntel, rng: Random) -> CellIntel:
    if existing is None:
        return incoming
    return CellIntel(
        resources=_merge_record(existing.resources, incoming.resources, rng),
        monsters=_merge_record(existing.monsters, incoming.monsters, rng),
    )


def _merge_record(
    existing: Optional[IntelRecord], incoming: Optional[IntelRecord], rng: Random
) -> Optional[IntelRecord]:
    if incoming is None:
        return existing
    if existing is None:
        return incoming
    return rng.choice([existing, incoming])
