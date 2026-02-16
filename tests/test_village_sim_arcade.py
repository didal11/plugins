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


def test_stable_layer_color_is_deterministic():
    import village_sim

    c1 = village_sim._stable_layer_color("Road")
    c2 = village_sim._stable_layer_color("Road")
    c3 = village_sim._stable_layer_color("Wall")

    assert c1 == c2
    assert c1 != c3


def test_build_render_npcs_from_templates(monkeypatch):
    import village_sim
    from ldtk_integration import GameWorld

    monkeypatch.setattr(
        village_sim,
        "load_npc_templates",
        lambda: [
            {"name": "엘린", "job": "모험가"},
            {"name": "보른", "job": "대장장이", "x": 3, "y": 4},
        ],
    )

    world = GameWorld(level_id="L", grid_size=16, width_px=160, height_px=160, entities=[], tiles=[])
    rows = village_sim._build_render_npcs(world)

    assert len(rows) == 2
    assert rows[0].name == "엘린"
    assert rows[0].x >= 0 and rows[0].y >= 0
    assert rows[1].x == 3 and rows[1].y == 4
