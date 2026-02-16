#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""LDtk -> Arcade domain loader.

This module is intentionally built around the requested stack:
- pydantic: schema validation
- orjson: payload parsing

It does not provide stdlib fallbacks; malformed or incompatible data raises
explicit validation errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import orjson
from pydantic import BaseModel, ConfigDict, Field


class LdtkFieldInstance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identifier: str = Field(alias="__identifier")
    value: Any = Field(alias="__value")


class LdtkEntityInstance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identifier: str = Field(alias="__identifier")
    px: List[int]
    field_instances: List[LdtkFieldInstance] = Field(default_factory=list, alias="fieldInstances")


class LdtkTileInstance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    px: List[int]
    tile_id: int = Field(alias="t")


class LdtkLayerInstance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identifier: str = Field(alias="__identifier")
    layer_type: str = Field(alias="__type")
    grid_size: Optional[int] = Field(default=None, alias="__gridSize")
    entity_instances: List[LdtkEntityInstance] = Field(default_factory=list, alias="entityInstances")
    grid_tiles: List[LdtkTileInstance] = Field(default_factory=list, alias="gridTiles")
    auto_layer_tiles: List[LdtkTileInstance] = Field(default_factory=list, alias="autoLayerTiles")


class LdtkLevel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identifier: str
    world_grid_size: Optional[int] = Field(default=None, alias="worldGridSize")
    px_wid: int = Field(alias="pxWid")
    px_hei: int = Field(alias="pxHei")
    layer_instances: Optional[List[LdtkLayerInstance]] = Field(default=None, alias="layerInstances")


class LdtkProject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_grid_size: Optional[int] = Field(default=None, alias="defaultGridSize")
    levels: List[LdtkLevel]


class GameEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    x: int
    y: int
    max_quantity: int
    current_quantity: int
    is_workbench: bool
    is_discovered: bool


class GameTile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: str
    name: str
    tile_id: int
    x: int
    y: int


class GameWorld(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_id: str
    grid_size: int
    width_px: int
    height_px: int
    entities: List[GameEntity]
    tiles: List[GameTile] = Field(default_factory=list)


def _fields_to_map(fields: List[LdtkFieldInstance]) -> Dict[str, Any]:
    return {f.identifier: f.value for f in fields}


def _as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"1", "true", "yes", "y", "on"}:
            return True
        if s in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _entity_from_ldtk(row: LdtkEntityInstance, *, grid_size: int) -> GameEntity:
    f = _fields_to_map(row.field_instances)
    key = str(f.get("key") or row.identifier).strip()
    if not key:
        raise ValueError("LDtk entity key cannot be empty")

    name = str(f.get("name") or key).strip() or key
    max_q = max(1, int(f.get("max_quantity", f.get("maxQuantity", 1))))
    current_q = int(f.get("current_quantity", f.get("currentQuantity", max_q)))
    current_q = max(0, min(max_q, current_q))

    is_workbench = _as_bool(f.get("is_workbench", f.get("isWorkbench", False)), False)
    is_discovered = True if is_workbench else _as_bool(f.get("is_discovered", f.get("isDiscovered", False)), False)

    tx = int(row.px[0] // grid_size)
    ty = int(row.px[1] // grid_size)

    return GameEntity(
        key=key,
        name=name,
        x=tx,
        y=ty,
        max_quantity=max_q,
        current_quantity=current_q,
        is_workbench=is_workbench,
        is_discovered=is_discovered,
    )


def _tiles_from_layer(layer: LdtkLayerInstance, *, fallback_grid_size: int) -> List[GameTile]:
    layer_grid = layer.grid_size or fallback_grid_size
    rows = [*layer.grid_tiles, *layer.auto_layer_tiles]
    return [
        GameTile(
            layer=layer.identifier,
            name=layer.identifier,
            tile_id=row.tile_id,
            x=int(row.px[0] // layer_grid),
            y=int(row.px[1] // layer_grid),
        )
        for row in rows
    ]


def load_ldtk_project(path: str | Path) -> LdtkProject:
    payload = orjson.loads(Path(path).read_bytes())
    return LdtkProject.model_validate(payload)


def build_world_from_ldtk(path: str | Path, *, level_identifier: Optional[str] = None, entity_layer: str = "Entities") -> GameWorld:
    project = load_ldtk_project(path)
    if not project.levels:
        raise ValueError("LDtk project has no levels")

    level = (
        next((lv for lv in project.levels if lv.identifier == level_identifier), None)
        if level_identifier
        else project.levels[0]
    )
    if level is None:
        raise ValueError(f"Level not found: {level_identifier}")

    layer_instances = level.layer_instances or []
    entity_layer_row = next(
        (
            layer
            for layer in layer_instances
            if layer.identifier == entity_layer and layer.layer_type == "Entities"
        ),
        None,
    )

    resolved_grid_size = level.world_grid_size
    if resolved_grid_size is None and entity_layer_row is not None:
        resolved_grid_size = entity_layer_row.grid_size
    if resolved_grid_size is None:
        resolved_grid_size = next((layer.grid_size for layer in layer_instances if layer.grid_size is not None), None)
    if resolved_grid_size is None:
        resolved_grid_size = project.default_grid_size
    if resolved_grid_size is None:
        resolved_grid_size = 16

    entities: List[GameEntity] = []
    if entity_layer_row is not None:
        entities = [_entity_from_ldtk(row, grid_size=resolved_grid_size) for row in entity_layer_row.entity_instances]

    tiles: List[GameTile] = []
    for layer in layer_instances:
        if layer.layer_type in {"Tiles", "AutoLayer"}:
            tiles.extend(_tiles_from_layer(layer, fallback_grid_size=resolved_grid_size))

    return GameWorld(
        level_id=level.identifier,
        grid_size=resolved_grid_size,
        width_px=level.px_wid,
        height_px=level.px_hei,
        entities=entities,
        tiles=tiles,
    )


def world_entities_as_rows(world: GameWorld) -> List[Dict[str, object]]:
    return [entity.model_dump() for entity in world.entities]


def world_tiles_as_rows(world: GameWorld) -> List[Dict[str, object]]:
    return [tile.model_dump() for tile in world.tiles]
