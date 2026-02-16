from __future__ import annotations

import json
from pathlib import Path
import importlib.util

import pytest

HAS_DEPS = importlib.util.find_spec("pydantic") is not None and importlib.util.find_spec("orjson") is not None

if HAS_DEPS:
    from ldtk_integration import build_world_from_ldtk, load_ldtk_project, world_entities_as_rows, world_tiles_as_rows


SAMPLE_LDTK = {
    "levels": [
        {
            "identifier": "World",
            "worldGridSize": 16,
            "pxWid": 640,
            "pxHei": 480,
            "layerInstances": [
                {
                    "__identifier": "Entities",
                    "__type": "Entities",
                    "entityInstances": [
                        {
                            "__identifier": "guild_board",
                            "px": [320, 160],
                            "fieldInstances": [
                                {"__identifier": "name", "__value": "길드 게시판"},
                                {"__identifier": "key", "__value": "guild_board"},
                                {"__identifier": "max_quantity", "__value": 9999},
                                {"__identifier": "is_workbench", "__value": True},
                            ],
                        },
                        {
                            "__identifier": "field",
                            "px": [480, 208],
                            "fieldInstances": [
                                {"__identifier": "name", "__value": "밭"},
                                {"__identifier": "maxQuantity", "__value": 200},
                                {"__identifier": "currentQuantity", "__value": 150},
                                {"__identifier": "isDiscovered", "__value": False},
                            ],
                        },
                    ],
                },
                {
                    "__identifier": "Road",
                    "__type": "Tiles",
                    "__gridSize": 16,
                    "gridTiles": [
                        {"px": [16, 32], "t": 7},
                        {"px": [48, 64], "t": 8}
                    ],
                }
            ],
        }
    ]
}



SAMPLE_LDTK_WITHOUT_ANY_GRID_SIZE = {
    "levels": [
        {
            "identifier": "NoGrid",
            "worldGridSize": None,
            "pxWid": 320,
            "pxHei": 160,
            "layerInstances": [
                {
                    "__identifier": "Entities",
                    "__type": "Entities",
                    "entityInstances": [
                        {"__identifier": "rock", "px": [32, 48], "fieldInstances": []}
                    ],
                }
            ],
        }
    ]
}

SAMPLE_LDTK_WITH_DEFAULT_GRID = {
    "defaultGridSize": 24,
    "levels": [
        {
            "identifier": "World",
            "worldGridSize": None,
            "pxWid": 480,
            "pxHei": 240,
            "layerInstances": [
                {
                    "__identifier": "Entities",
                    "__type": "Entities",
                    "entityInstances": [
                        {"__identifier": "tree", "px": [48, 72], "fieldInstances": []}
                    ],
                }
            ],
        }
    ],
}



SAMPLE_LDTK_WITHOUT_ANY_GRID_SIZE = {
    "levels": [
        {
            "identifier": "NoGrid",
            "worldGridSize": None,
            "pxWid": 320,
            "pxHei": 160,
            "layerInstances": [
                {
                    "__identifier": "Entities",
                    "__type": "Entities",
                    "entityInstances": [
                        {"__identifier": "rock", "px": [32, 48], "fieldInstances": []}
                    ],
                }
            ],
        }
    ]
}

SAMPLE_LDTK_WITH_DEFAULT_GRID = {
    "defaultGridSize": 24,
    "levels": [
        {
            "identifier": "World",
            "worldGridSize": None,
            "pxWid": 480,
            "pxHei": 240,
            "layerInstances": [
                {
                    "__identifier": "Entities",
                    "__type": "Entities",
                    "entityInstances": [
                        {"__identifier": "tree", "px": [48, 72], "fieldInstances": []}
                    ],
                }
            ],
        }
    ],
}


@pytest.mark.skipif(not HAS_DEPS, reason="requires pydantic and orjson")
def test_load_ldtk_project_and_build_world(tmp_path: Path):
    ldtk_file = tmp_path / "sample.ldtk"
    ldtk_file.write_text(json.dumps(SAMPLE_LDTK), encoding="utf-8")

    project = load_ldtk_project(ldtk_file)
    assert len(project.levels) == 1

    world = build_world_from_ldtk(ldtk_file)
    assert world.level_id == "World"
    assert world.grid_size == 16
    assert world.width_px == 640
    assert world.height_px == 480
    assert len(world.entities) == 2

    rows = world_entities_as_rows(world)
    assert rows[0]["x"] == 20
    assert rows[0]["y"] == 10
    assert rows[0]["is_workbench"] is True
    assert rows[1]["x"] == 30
    assert rows[1]["y"] == 13
    assert rows[1]["current_quantity"] == 150

    tile_rows = world_tiles_as_rows(world)
    assert len(tile_rows) == 2
    assert tile_rows[0]["layer"] == "Road"
    assert tile_rows[0]["x"] == 1
    assert tile_rows[0]["y"] == 2


@pytest.mark.skipif(not HAS_DEPS, reason="requires pydantic and orjson")
def test_build_world_raises_for_missing_level(tmp_path: Path):
    ldtk_file = tmp_path / "sample.ldtk"
    ldtk_file.write_text(json.dumps(SAMPLE_LDTK), encoding="utf-8")

    with pytest.raises(ValueError, match="Level not found"):
        build_world_from_ldtk(ldtk_file, level_identifier="Nope")


@pytest.mark.skipif(not HAS_DEPS, reason="requires pydantic and orjson")
def test_build_world_uses_default_grid_when_level_grid_is_missing(tmp_path: Path):
    ldtk_file = tmp_path / "sample_default_grid.ldtk"
    ldtk_file.write_text(json.dumps(SAMPLE_LDTK_WITH_DEFAULT_GRID), encoding="utf-8")

    world = build_world_from_ldtk(ldtk_file)
    assert world.grid_size == 24
    assert world.entities[0].x == 2
    assert world.entities[0].y == 3


@pytest.mark.skipif(not HAS_DEPS, reason="requires pydantic and orjson")
def test_build_world_falls_back_to_default_tile_when_grid_is_missing_everywhere(tmp_path: Path):
    ldtk_file = tmp_path / "sample_no_grid.ldtk"
    ldtk_file.write_text(json.dumps(SAMPLE_LDTK_WITHOUT_ANY_GRID_SIZE), encoding="utf-8")

    world = build_world_from_ldtk(ldtk_file)
    assert world.grid_size == 16
    assert world.entities[0].x == 2
    assert world.entities[0].y == 3


@pytest.mark.skipif(not HAS_DEPS, reason="requires pydantic and orjson")
def test_build_world_collects_blocked_tiles_from_collision_and_wall(tmp_path: Path):
    sample = {
        "defs": {
            "layers": [
                {
                    "uid": 10,
                    "identifier": "Collision",
                    "intGridValues": [{"value": 1, "identifier": "wall"}],
                }
            ]
        },
        "levels": [
            {
                "identifier": "World",
                "worldGridSize": 16,
                "pxWid": 32,
                "pxHei": 32,
                "layerInstances": [
                    {"__identifier": "Entities", "__type": "Entities", "entityInstances": []},
                    {
                        "__identifier": "Collision",
                        "__type": "IntGrid",
                        "layerDefUid": 10,
                        "__cWid": 2,
                        "__cHei": 2,
                        "__gridSize": 16,
                        "intGridCsv": [1, 0, 0, 0],
                    },
                    {
                        "__identifier": "Wall",
                        "__type": "Tiles",
                        "__gridSize": 16,
                        "gridTiles": [{"px": [16, 16], "t": 1}],
                    },
                ],
            }
        ],
    }
    ldtk_file = tmp_path / "sample_collision.ldtk"
    ldtk_file.write_text(json.dumps(sample), encoding="utf-8")

    world = build_world_from_ldtk(ldtk_file)
    assert sorted(world.blocked_tiles) == [[0, 0], [1, 1]]
