from __future__ import annotations

import importlib.util
import sys

import pytest

HAS_ARCADE = importlib.util.find_spec("arcade") is not None


@pytest.mark.skipif(not HAS_ARCADE, reason="requires arcade")
def test_village_sim_uses_arcade_and_not_pygame(monkeypatch):
    import village_sim

    monkeypatch.setattr(
        village_sim,
        "load_entities",
        lambda: [
            {
                "key": "guild_board",
                "name": "길드 게시판",
                "x": 10,
                "y": 5,
                "max_quantity": 999,
                "current_quantity": 999,
                "is_workbench": True,
                "is_discovered": True,
            }
        ],
    )

    world = village_sim.world_from_entities_json()
    assert world.entities[0].key == "guild_board"
    source = __import__("inspect").getsource(village_sim)
    assert "import pygame" not in source


def test_parse_args_defaults_to_data_map(monkeypatch):
    import village_sim

    monkeypatch.setattr(sys, "argv", ["village_sim.py"])
    args = village_sim._parse_args()

    assert args.ldtk.endswith("data/map.ldtk")


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

    sim = village_sim.SimulationRuntime(world, npcs, seed=1, start_hour=8)

    sim.tick_once()  # 08시, 식사 시간
    assert sim.state_by_name["A"].current_action == "식사"

    sim.start_hour = 9
    sim.ticks = 0
    sim.state_by_name["A"].ticks_remaining = 0
    sim.tick_once()  # 09시, 업무 시간
    assert sim.state_by_name["A"].current_action == "농사"

    sim.start_hour = 22
    sim.ticks = 0
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
            village_sim.GameEntity(
                key="dining_table",
                name="식탁",
                x=3,
                y=1,
                max_quantity=1,
                current_quantity=1,
                is_workbench=True,
                is_discovered=True,
            )
        ],
        tiles=[],
        blocked_tiles=[[2, 1]],
    )
    npcs = [village_sim.RenderNpc(name="A", job="농부", x=1, y=1)]
    sim = village_sim.SimulationRuntime(world, npcs, seed=1, start_hour=8)

    sim.tick_once()
    assert sim.state_by_name["A"].current_action == "식사"
    assert (npcs[0].x, npcs[0].y) == (1, 0)


def test_display_clock_starts_from_year_zero_and_advances_10_minutes(monkeypatch):
    import village_sim

    monkeypatch.setattr(village_sim, "load_job_defs", lambda: [])
    monkeypatch.setattr(village_sim, "load_action_defs", lambda: [])

    world = village_sim.GameWorld(level_id="W", grid_size=16, width_px=32, height_px=32, entities=[], tiles=[])
    sim = village_sim.SimulationRuntime(world, [], seed=1)

    assert sim.display_clock() == "0000년 01월 01일 00:00"
    sim.tick_once()
    assert sim.display_clock() == "0000년 01월 01일 00:10"


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

    sim = village_sim.SimulationRuntime(world, npcs, seed=1, start_hour=11)

    sim.tick_once()  # 11시 업무 시작
    assert sim.state_by_name["A"].current_action == "장기작업"

    for _ in range(6):
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

    sim = village_sim.SimulationRuntime(world, npcs, seed=1, start_hour=19)

    sim.tick_once()  # 19시 업무 시작
    assert sim.state_by_name["A"].current_action == "장기작업"

    for _ in range(6):
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

    sim = village_sim.SimulationRuntime(world, npcs, seed=1, start_hour=8)
    sim._pick_next_work_action = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("업무 선택 로직 호출되면 안됨"))

    sim.tick_once()  # 08시 식사
    assert sim.state_by_name["A"].current_action == "식사"

    sim.start_hour = 22
    sim.ticks = 0
    sim.state_by_name["A"].ticks_remaining = 0
    sim.tick_once()  # 22시 취침
    assert sim.state_by_name["A"].current_action == "취침"
