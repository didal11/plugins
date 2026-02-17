from __future__ import annotations

import importlib.util
import sys

import pytest

HAS_ARCADE = importlib.util.find_spec("arcade") is not None


def _set_sim_time(sim, hour: int, minute: int = 0) -> None:
    sim.ticks = ((hour % 24) * 60) + (minute % 60) - 1
    for state in sim.state_by_name.values():
        state.decision_ticks_until_check = 0


@pytest.mark.skipif(not HAS_ARCADE, reason="requires arcade")
def test_village_sim_uses_arcade_and_not_pygame():
    import village_sim

    source = __import__("inspect").getsource(village_sim)
    assert "import pygame" not in source
    assert "world_from_entities_json" not in source


def test_parse_args_defaults_to_data_map(monkeypatch):
    import village_sim

    monkeypatch.setattr(sys, "argv", ["village_sim.py"])
    args = village_sim._parse_args()

    assert args.ldtk.endswith("data/map.ldtk")
    assert args.all_levels is False


def test_parse_args_all_levels_flag(monkeypatch):
    import village_sim

    monkeypatch.setattr(sys, "argv", ["village_sim.py", "--all-levels"])
    args = village_sim._parse_args()

    assert args.all_levels is True


def test_build_render_npcs_uses_defaults_and_clamps(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_npc_templates",
        lambda: [
            {"name": "A", "job": "농부"},
            {"name": "B", "job": "약사", "x": 999, "y": -5},
        ],
    )

    world = village_sim.GameWorld(
        level_id="World",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[],
        tiles=[],
    )

    npcs = village_sim._build_render_npcs(world)
    assert len(npcs) == 2
    assert 0 <= npcs[0].x <= 3
    assert 0 <= npcs[0].y <= 3
    assert (npcs[1].x, npcs[1].y) == (3, 0)


def test_build_render_npcs_prefers_town_region(monkeypatch):
    import village_sim
    from ldtk_integration import LevelRegion

    monkeypatch.setattr(
        village_sim,
        "load_npc_templates",
        lambda: [{"name": "A", "job": "농부"}],
    )

    world = village_sim.GameWorld(
        level_id="ALL_LEVELS",
        grid_size=16,
        width_px=160,
        height_px=160,
        entities=[],
        tiles=[],
        level_regions=[LevelRegion(level_id="Town", x=1, y=2, width=3, height=2)],
    )

    npcs = village_sim._build_render_npcs(world)
    assert len(npcs) == 1
    assert 1 <= npcs[0].x <= 3
    assert 2 <= npcs[0].y <= 3


def test_simulation_runtime_uses_daily_planning_for_actions(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "농부", "work_actions": ["농사"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [{"name": "농사", "duration_minutes": 10}],
    )

    world = village_sim.GameWorld(level_id="W", grid_size=16, width_px=64, height_px=64, entities=[], tiles=[])
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]

    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    _set_sim_time(sim, 8)
    sim.tick_once()  # 08시, 식사 시간
    assert sim.state_by_name["A"].current_action == "식사"

    _set_sim_time(sim, 9)
    sim.state_by_name["A"].ticks_remaining = 0
    sim.tick_once()  # 09시, 업무 시간
    assert sim.state_by_name["A"].current_action == "농사"

    _set_sim_time(sim, 22)
    sim.state_by_name["A"].ticks_remaining = 0
    sim.tick_once()  # 22시, 취침 시간
    assert sim.state_by_name["A"].current_action == "취침"


def test_simulation_runtime_meal_moves_towards_dining_table(monkeypatch):
    import village_sim

    monkeypatch.setattr(village_sim, "load_job_defs", lambda: [{"job": "농부", "work_actions": ["농사"]}])
    monkeypatch.setattr(village_sim, "load_action_defs", lambda: [{"name": "농사", "duration_minutes": 10}])

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="dining_table",
                name="식탁",
                x=3,
                y=1,
                max_quantity=1,
                current_quantity=1,
                is_discovered=True,
            )
        ],
        tiles=[],
        blocked_tiles=[[2, 1]],
    )
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    _set_sim_time(sim, 8)
    sim.tick_once()
    assert sim.state_by_name["A"].current_action == "식사"
    assert (npcs[0].x, npcs[0].y) == (1, 0)





def test_simulation_runtime_work_moves_towards_required_entity(monkeypatch):
    import village_sim

    monkeypatch.setattr(village_sim, "load_job_defs", lambda: [{"job": "농부", "work_actions": ["농사"]}])
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [{"name": "농사", "duration_minutes": 10, "required_entity": "field"}],
    )

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="field",
                name="농지",
                x=3,
                y=1,
                max_quantity=5,
                current_quantity=5,
                is_discovered=True
            )
        ],
        tiles=[],
        blocked_tiles=[[2, 1]],
    )
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    _set_sim_time(sim, 9)
    sim.tick_once()

    assert sim.state_by_name["A"].current_action == "농사"
    assert (npcs[0].x, npcs[0].y) == (1, 0)
def test_simulation_runtime_sleep_moves_towards_bed(monkeypatch):
    import village_sim

    monkeypatch.setattr(village_sim, "load_job_defs", lambda: [{"job": "농부", "work_actions": ["농사"]}])
    monkeypatch.setattr(village_sim, "load_action_defs", lambda: [{"name": "농사", "duration_minutes": 10}])

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="bed_single",
                name="침대",
                x=3,
                y=1,
                max_quantity=1,
                current_quantity=1,
                is_discovered=True,
            )
        ],
        tiles=[],
        blocked_tiles=[[2, 1]],
    )
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    _set_sim_time(sim, 22)
    sim.tick_once()
    assert sim.state_by_name["A"].current_action == "취침"
    assert (npcs[0].x, npcs[0].y) == (1, 0)

def test_display_clock_starts_from_year_zero_and_advances_1_minute(monkeypatch):
    import village_sim

    monkeypatch.setattr(village_sim, "load_job_defs", lambda: [])
    monkeypatch.setattr(village_sim, "load_action_defs", lambda: [])

    world = village_sim.GameWorld(level_id="W", grid_size=16, width_px=32, height_px=32, entities=[], tiles=[])
    sim = village_sim.SimulationRuntime(world, [], seed=1)

    assert sim.display_clock() == "0000년 01월 01일 00:00"
    sim.tick_once()
    assert sim.display_clock() == "0000년 01월 01일 00:01"


def test_is_guild_board_entity_matches_board_keyword():
    import village_sim

    board = village_sim.GameEntity(key="guild_board", name="모험가 게시판", x=0, y=0)
    not_board = village_sim.GameEntity(key="tree_oak", name="참나무", x=1, y=1)

    assert village_sim._is_guild_board_entity(board) is True
    assert village_sim._is_guild_board_entity(not_board) is False


def test_format_guild_issue_lines_returns_readable_rows(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "모험가", "work_actions": ["게시판확인", "탐색", "약초채집"]}],
    )
    monkeypatch.setattr(village_sim, "load_action_defs", lambda: [{"name": "탐색", "duration_minutes": 10}])

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="herb",
                name="약초",
                x=1,
                y=1,
                max_quantity=1,
                current_quantity=1,
                is_discovered=False,
            )
        ],
        tiles=[],
    )
    sim = village_sim.SimulationRuntime(world, [village_sim.RenderNpc(name="A", job="모험가", x=0, y=0)], seed=1)
    sim.target_available_by_key = {"herb": 2}
    sim.target_stock_by_key = {"herb": 0}

    lines = village_sim._format_guild_issue_lines(sim)
    assert lines
    assert "약초 탐색" in lines[0]
    assert "자원:약초" in lines[0]


def test_pick_entity_near_world_point_prefers_nearest_entity():
    import village_sim

    entities = [
        village_sim.GameEntity(key="guild_board", name="게시판", x=2, y=2),
        village_sim.GameEntity(key="tree_oak", name="나무", x=4, y=2),
    ]
    tile = 16
    world_h = 128

    board_center_x = (2 * tile) + (tile / 2)
    board_center_y = world_h - ((2 * tile) + (tile / 2))
    selected = village_sim._pick_entity_near_world_point(
        entities,
        board_center_x + 2,
        board_center_y - 1,
        tile_size=tile,
        world_height_px=world_h,
    )

    assert selected is not None
    assert selected.name == "게시판"

def test_display_clock_hud_rounds_down_to_30_minutes(monkeypatch):
    import village_sim

    monkeypatch.setattr(village_sim, "load_job_defs", lambda: [])
    monkeypatch.setattr(village_sim, "load_action_defs", lambda: [])

    world = village_sim.GameWorld(level_id="W", grid_size=16, width_px=32, height_px=32, entities=[], tiles=[])
    sim = village_sim.SimulationRuntime(world, [], seed=1)

    sim.ticks = 29
    assert sim.display_clock_by_interval(30) == "0000년 01월 01일 00:00"

    sim.ticks = 30
    assert sim.display_clock_by_interval(30) == "0000년 01월 01일 00:30"

    sim.ticks = 61
    assert sim.display_clock_by_interval(30) == "0000년 01월 01일 01:00"



def test_simulation_runtime_planning_preempts_ongoing_work(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "농부", "work_actions": ["장기작업"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [{"name": "장기작업", "duration_minutes": 180}],
    )

    world = village_sim.GameWorld(level_id="W", grid_size=16, width_px=64, height_px=64, entities=[], tiles=[])
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]

    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    _set_sim_time(sim, 11)
    sim.tick_once()  # 11시 업무 시작
    assert sim.state_by_name["A"].current_action == "장기작업"

    for _ in range(60):
        sim.tick_once()  # 12시 진입
    assert sim.state_by_name["A"].current_action == "식사"


def test_simulation_runtime_planning_preempts_ongoing_work_for_sleep(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "농부", "work_actions": ["장기작업"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [{"name": "장기작업", "duration_minutes": 180}],
    )

    world = village_sim.GameWorld(level_id="W", grid_size=16, width_px=64, height_px=64, entities=[], tiles=[])
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]

    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    _set_sim_time(sim, 19)
    sim.tick_once()  # 19시 업무 시작
    assert sim.state_by_name["A"].current_action == "장기작업"

    for _ in range(60):
        sim.tick_once()  # 20시 진입
    assert sim.state_by_name["A"].current_action == "취침"


def test_simulation_runtime_does_not_select_work_during_meal_or_sleep(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "농부", "work_actions": ["농사"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [{"name": "농사", "duration_minutes": 10}],
    )

    world = village_sim.GameWorld(level_id="W", grid_size=16, width_px=64, height_px=64, entities=[], tiles=[])
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]

    sim = village_sim.SimulationRuntime(world, npcs, seed=1)
    sim._pick_next_work_action = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("업무 선택 로직 호출되면 안됨"))

    _set_sim_time(sim, 8)
    sim.tick_once()  # 08시 식사
    assert sim.state_by_name["A"].current_action == "식사"

    _set_sim_time(sim, 22)
    sim.state_by_name["A"].ticks_remaining = 0
    sim.tick_once()  # 22시 취침
    assert sim.state_by_name["A"].current_action == "취침"


def test_simulation_runtime_updates_decision_once_per_10_ticks(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "농부", "work_actions": ["농사"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [{"name": "농사", "duration_minutes": 1}],
    )

    world = village_sim.GameWorld(level_id="W", grid_size=16, width_px=64, height_px=64, entities=[], tiles=[])
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]

    sim = village_sim.SimulationRuntime(world, npcs, seed=1)
    _set_sim_time(sim, 9)

    called = 0

    def _count_pick(npc, state):
        nonlocal called
        called += 1
        state.current_action = "농사"
        state.ticks_remaining = 1

    sim._pick_next_work_action = _count_pick

    for _ in range(10):
        sim.tick_once()
    assert called == 1

    sim.tick_once()
    assert called == 2


def test_sleep_does_not_recalculate_bed_path_every_tick(monkeypatch):
    import village_sim

    monkeypatch.setattr(village_sim, "load_job_defs", lambda: [{"job": "농부", "work_actions": ["농사"]}])
    monkeypatch.setattr(village_sim, "load_action_defs", lambda: [{"name": "농사", "duration_minutes": 10}])

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="bed_single",
                name="침대",
                x=3,
                y=1,
                max_quantity=1,
                current_quantity=1,
                is_discovered=True
            )
        ],
        tiles=[],
    )
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    calls = 0
    original = sim._find_path_to_nearest_target

    def wrapped(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    sim._find_path_to_nearest_target = wrapped

    _set_sim_time(sim, 22)
    sim.tick_once()
    sim.tick_once()
    sim.tick_once()

    assert calls == 1


def test_sleep_stays_on_bed_after_arrival(monkeypatch):
    import village_sim

    monkeypatch.setattr(village_sim, "load_job_defs", lambda: [{"job": "농부", "work_actions": ["농사"]}])
    monkeypatch.setattr(village_sim, "load_action_defs", lambda: [{"name": "농사", "duration_minutes": 10}])

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="bed_single",
                name="침대",
                x=3,
                y=1,
                max_quantity=1,
                current_quantity=1,
                is_discovered=True
            )
        ],
        tiles=[],
        blocked_tiles=[[2, 1]],
    )
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    _set_sim_time(sim, 22)
    for _ in range(4):
        sim.tick_once()
    assert (npcs[0].x, npcs[0].y) == (3, 1)

    sim.tick_once()
    sim.tick_once()
    assert (npcs[0].x, npcs[0].y) == (3, 1)


def test_collect_render_entities_keeps_resource_entities_for_map_draw():
    import village_sim

    entities = [
        village_sim.ResourceEntity(
            key="tree",
            name="나무",
            x=1,
            y=1,
            max_quantity=1,
            current_quantity=1,
            is_discovered=True
        ),
        village_sim.StructureEntity(
            key="bed",
            name="침대",
            x=2,
            y=2,
            min_duration=1,
            max_duration=5,
            current_duration=5,
        ),
    ]

    collected = village_sim._collect_render_entities(entities)
    assert [e.name for e in collected] == ["나무", "침대"]


def test_adventurer_picks_only_from_guild_issued_actions(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "모험가", "work_actions": ["탐색", "약초채집", "벌목"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [
            {"name": "탐색", "duration_minutes": 10},
            {"name": "약초채집", "duration_minutes": 10, "required_entity": "herb"},
            {"name": "벌목", "duration_minutes": 10, "required_entity": "tree"},
        ],
    )

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="herb",
                name="약초",
                x=2,
                y=2,
                max_quantity=5,
                current_quantity=5,
                is_discovered=True,
            )
        ],
        tiles=[],
    )
    npcs = [village_sim.RenderNpc(name="A", job="모험가", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)
    sim.target_stock_by_key = {"herb": 7}
    sim.target_available_by_key = {"herb": 7}

    _set_sim_time(sim, 9)
    sim.tick_once()

    assert sim.state_by_name["A"].current_action in {"탐색", "약초채집"}
    if sim.state_by_name["A"].current_action == "탐색":
        assert sim.state_by_name["A"].current_action_display.endswith(" 탐색")
    assert sim.state_by_name["A"].current_action != "벌목"


def test_adventurer_checks_board_first_when_work_starts(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "모험가", "work_actions": ["게시판확인", "탐색", "약초채집"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [
            {"name": "게시판확인", "duration_minutes": 10, "required_entity": "guild_board"},
            {"name": "탐색", "duration_minutes": 10},
            {"name": "약초채집", "duration_minutes": 10, "required_entity": "herb"},
        ],
    )

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.StructureEntity(
                key="guild_board",
                name="길드 게시판",
                x=2,
                y=1,
                min_duration=1,
                max_duration=1,
                current_duration=1,
            ),
            village_sim.ResourceEntity(
                key="herb",
                name="약초",
                x=3,
                y=3,
                max_quantity=5,
                current_quantity=5,
                is_discovered=True,
            ),
        ],
        tiles=[],
    )
    npcs = [village_sim.RenderNpc(name="A", job="모험가", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)
    sim.target_stock_by_key = {"herb": 7}
    sim.target_available_by_key = {"herb": 7}

    _set_sim_time(sim, 9)
    sim.tick_once()
    assert sim.state_by_name["A"].current_action == "게시판확인"

    sim.state_by_name["A"].ticks_remaining = 0
    sim.state_by_name["A"].decision_ticks_until_check = 0
    sim.tick_once()
    assert sim.state_by_name["A"].current_action in {"탐색", "약초채집"}
    if sim.state_by_name["A"].current_action == "탐색":
        assert sim.state_by_name["A"].current_action_display.endswith(" 탐색")


def test_registered_resources_include_world_keys_and_available_follows_discovery(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "모험가", "work_actions": ["탐색", "약초채집"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [
            {"name": "탐색", "duration_minutes": 10},
            {"name": "약초채집", "duration_minutes": 10, "required_entity": "herb"},
        ],
    )

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="herb",
                name="약초",
                x=1,
                y=1,
                max_quantity=5,
                current_quantity=5,
                is_discovered=False,
            )
        ],
        tiles=[],
    )
    sim = village_sim.SimulationRuntime(world, [village_sim.RenderNpc(name="A", job="모험가", x=0, y=0)], seed=1)

    assert sim.guild_dispatcher.resource_keys == ["herb"]
    assert sim.guild_dispatcher.available_by_key["herb"] == 0
    assert sim.guild_inventory_by_key["herb"] == 0

    world.entities[0].is_discovered = True
    sim.tick_once()

    assert sim.guild_dispatcher.resource_keys == ["herb"]
    assert sim.guild_dispatcher.available_by_key["herb"] == 5
    assert sim.guild_inventory_by_key["herb"] == 0


def test_exploration_action_is_linked_with_frontier_exploration_state(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "모험가", "work_actions": ["탐색"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [{"name": "탐색", "duration_minutes": 10}],
    )

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=64,
        height_px=64,
        entities=[
            village_sim.ResourceEntity(
                key="herb",
                name="약초",
                x=3,
                y=3,
                max_quantity=5,
                current_quantity=5,
                is_discovered=False,
            )
        ],
        tiles=[],
    )
    npcs = [village_sim.RenderNpc(name="A", job="모험가", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    initial_known_count = len(sim.guild_board_exploration_state.known_cells)
    _set_sim_time(sim, 9)
    sim.tick_once()
    sim.tick_once()
    sim.tick_once()

    assert sim.state_by_name["A"].current_action == "탐색"
    assert sim.state_by_name["A"].current_action_display.endswith(" 탐색")
    assert len(sim.guild_board_exploration_state.known_cells) > initial_known_count


def test_simulation_runtime_marks_town_cells_known_on_start():
    import village_sim
    from ldtk_integration import LevelRegion

    world = village_sim.GameWorld(
        level_id="ALL_LEVELS",
        grid_size=16,
        width_px=80,
        height_px=80,
        entities=[],
        tiles=[],
        blocked_tiles=[[2, 2]],
        level_regions=[LevelRegion(level_id="Town", x=1, y=1, width=3, height=3)],
    )
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=0, y=0)]

    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    assert (1, 1) in sim.guild_board_exploration_state.known_cells
    assert (3, 3) in sim.guild_board_exploration_state.known_cells
    assert (2, 2) not in sim.guild_board_exploration_state.known_cells


def test_exploration_reveals_surrounding_8_cells_after_move(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_job_defs",
        lambda: [{"job": "모험가", "work_actions": ["탐색"]}],
    )
    monkeypatch.setattr(
        village_sim,
        "load_action_defs",
        lambda: [{"name": "탐색", "duration_minutes": 10}],
    )

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=96,
        height_px=96,
        entities=[],
        tiles=[],
    )
    npcs = [village_sim.RenderNpc(name="A", job="모험가", x=3, y=3)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    npc = npcs[0]
    state = sim.state_by_name["A"]
    moved = sim._step_exploration_action(npc, state, 6, 6)

    assert moved is True
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            assert (npc.x + dx, npc.y + dy) in sim.guild_board_exploration_state.known_cells


def test_mark_cell_discovered_updates_known_only_when_adjacent_frontier_exists():
    import village_sim

    world = village_sim.GameWorld(
        level_id="W",
        grid_size=16,
        width_px=96,
        height_px=96,
        entities=[],
        tiles=[],
    )
    npcs = [village_sim.RenderNpc(name="A", job="모험가", x=0, y=0)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1)

    sim.guild_board_exploration_state.frontier_cells.clear()

    sim._mark_cell_discovered((5, 5))
    assert (5, 5) not in sim.guild_board_exploration_state.known_cells

    sim.guild_board_exploration_state.frontier_cells.add((4, 4))
    sim._mark_cell_discovered((5, 5))
    assert (5, 5) in sim.guild_board_exploration_state.known_cells
