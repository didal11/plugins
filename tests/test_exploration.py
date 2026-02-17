from random import Random

from exploration import GuildBoardExplorationState
from exploration import NPCExplorationBuffer
from exploration import choose_next_frontier


def test_apply_npc_buffer_updates_only_delta_sets():
    board = GuildBoardExplorationState(known_cells={(0, 0)})
    delta = NPCExplorationBuffer(new_known_cells={(2, 2)})

    board.apply_npc_buffer(delta, Random(1))

    assert board.known_cells == {(0, 0), (2, 2)}


def test_apply_npc_buffer_applies_resource_updates_and_removals():
    board = GuildBoardExplorationState(known_resources={("herb", (1, 1)): 3})
    delta = NPCExplorationBuffer(
        known_resource_updates={("herb", (1, 1)): 5, ("ore", (2, 2)): 1},
        known_resource_removals={("ore", (9, 9))},
    )

    board.apply_npc_buffer(delta, Random(0))

    assert board.known_resources == {
        ("herb", (1, 1)): 5,
        ("ore", (2, 2)): 1,
    }


def test_apply_npc_buffer_adds_monster_discoveries_only():
    board = GuildBoardExplorationState(known_monsters={("slime", (0, 0))})
    delta = NPCExplorationBuffer(known_monster_discoveries={("slime", (0, 0)), ("wolf", (1, 1))})

    board.apply_npc_buffer(delta, Random(7))

    assert board.known_monsters == {("slime", (0, 0)), ("wolf", (1, 1))}


def test_buffer_records_resource_deltas_only_on_change():
    board = GuildBoardExplorationState(known_resources={("herb", (1, 1)): 2})
    buffer = NPCExplorationBuffer()

    buffer.record_resource_observation("herb", (1, 1), 2, board.known_resources)
    assert buffer.known_resource_updates == {}

    buffer.record_resource_observation("herb", (1, 1), 4, board.known_resources)
    assert buffer.known_resource_updates == {("herb", (1, 1)): 4}

    buffer.record_resource_absence("herb", (1, 1), board.known_resources)
    assert buffer.known_resource_updates == {}
    assert buffer.known_resource_removals == {("herb", (1, 1))}


def test_choose_next_frontier_returns_none_when_empty():
    assert choose_next_frontier([], Random(7)) is None


def test_export_delta_for_known_cells_filters_cells():
    board = GuildBoardExplorationState(
        known_cells={(0, 0), (9, 9)},
        known_resources={("herb", (0, 0)): 2, ("ore", (2, 2)): 1},
        known_monsters={("slime", (0, 0)), ("bat", (5, 5))},
    )

    delta = board.export_delta_for_known_cells({(0, 0), (1, 1)})

    assert delta.new_known_cells == {(0, 0)}
    assert delta.known_resource_updates == {("herb", (0, 0)): 2}
    assert delta.known_monster_discoveries == {("slime", (0, 0))}


def test_with_all_cells_known_initializes_full_grid():
    board = GuildBoardExplorationState.with_all_cells_known(2, 3)

    assert board.known_cells == {
        (0, 0), (0, 1), (0, 2),
        (1, 0), (1, 1), (1, 2),
    }
