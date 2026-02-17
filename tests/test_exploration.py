from random import Random

from exploration import CellIntel
from exploration import GuildBoardExplorationState
from exploration import IntelRecord
from exploration import NPCExplorationBuffer
from exploration import choose_next_frontier


def test_apply_npc_buffer_updates_only_delta_sets():
    board = GuildBoardExplorationState(known_cells={(0, 0)}, frontier_cells={(1, 1)})
    delta = NPCExplorationBuffer(new_known_cells={(2, 2)}, new_frontier_cells={(3, 3)})

    board.apply_npc_buffer(delta, Random(1))

    assert board.known_cells == {(0, 0), (2, 2)}
    assert board.frontier_cells == {(1, 1), (3, 3)}


def test_apply_npc_buffer_merges_intel_with_random_choice():
    board = GuildBoardExplorationState(
        cell_intel={
            (1, 1): CellIntel(resources=IntelRecord(payload={"count": 1}, updated_at=1, discovered_by="a"))
        }
    )
    delta = NPCExplorationBuffer(
        intel_updates={
            (1, 1): CellIntel(resources=IntelRecord(payload={"count": 9}, updated_at=1, discovered_by="z"))
        }
    )

    board.apply_npc_buffer(delta, Random(0))

    merged = board.cell_intel[(1, 1)].resources
    assert merged is not None
    assert merged.payload in ({"count": 1}, {"count": 9})


def test_choose_next_frontier_returns_none_when_empty():
    assert choose_next_frontier([], Random(7)) is None


def test_export_delta_for_known_cells_filters_cells():
    board = GuildBoardExplorationState(
        known_cells={(0, 0), (9, 9)},
        frontier_cells={(0, 0), (5, 5)},
        cell_intel={(0, 0): CellIntel(monsters=IntelRecord(payload={"slime": 2}))},
    )

    delta = board.export_delta_for_known_cells({(0, 0), (1, 1)})

    assert delta.new_known_cells == {(0, 0)}
    assert delta.new_frontier_cells == {(0, 0)}
    assert set(delta.intel_updates.keys()) == {(0, 0)}

def test_with_all_cells_known_initializes_full_grid():
    board = GuildBoardExplorationState.with_all_cells_known(2, 3)

    assert board.known_cells == {
        (0, 0), (0, 1), (0, 2),
        (1, 0), (1, 1), (1, 2),
    }
    assert board.frontier_cells == set()
