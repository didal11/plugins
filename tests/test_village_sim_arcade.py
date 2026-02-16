from __future__ import annotations

import importlib.util

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
