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
    assert (npcs[0].x, npcs[0].y) == (1, 1)
    assert (npcs[1].x, npcs[1].y) == (3, 0)


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


def test_collect_non_resource_entities_filters_resource_tag():
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

    collected = village_sim._collect_non_resource_entities(entities)
    assert [e.name for e in collected] == ["침대"]


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
