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
