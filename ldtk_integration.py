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
import re
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
    tags: List[str] = Field(default_factory=list, alias="__tags")
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
    c_wid: Optional[int] = Field(default=None, alias="__cWid")
    c_hei: Optional[int] = Field(default=None, alias="__cHei")
    layer_def_uid: Optional[int] = Field(default=None, alias="layerDefUid")
    entity_instances: List[LdtkEntityInstance] = Field(default_factory=list, alias="entityInstances")
    grid_tiles: List[LdtkTileInstance] = Field(default_factory=list, alias="gridTiles")
    auto_layer_tiles: List[LdtkTileInstance] = Field(default_factory=list, alias="autoLayerTiles")
    int_grid_csv: List[int] = Field(default_factory=list, alias="intGridCsv")


class LdtkIntGridValueDef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: int
    identifier: Optional[str] = None


class LdtkLayerDef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uid: int
    identifier: str
    int_grid_values: List[LdtkIntGridValueDef] = Field(default_factory=list, alias="intGridValues")


class LdtkDefs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    layers: List[LdtkLayerDef] = Field(default_factory=list)


class LdtkLevel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identifier: str
    world_x: int = Field(default=0, alias="worldX")
    world_y: int = Field(default=0, alias="worldY")
    world_depth: int = Field(default=0, alias="worldDepth")
    world_grid_size: Optional[int] = Field(default=None, alias="worldGridSize")
    px_wid: int = Field(alias="pxWid")
    px_hei: int = Field(alias="pxHei")
    layer_instances: Optional[List[LdtkLayerInstance]] = Field(default=None, alias="layerInstances")


class LdtkProject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_grid_size: Optional[int] = Field(default=None, alias="defaultGridSize")
    levels: List[LdtkLevel]
    defs: LdtkDefs = Field(default_factory=LdtkDefs)


class GameEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    x: int
    y: int


class ResourceEntity(GameEntity):
    model_config = ConfigDict(extra="forbid")

    max_quantity: int
    current_quantity: int
    is_discovered: bool


class WorkbenchEntity(GameEntity):
    model_config = ConfigDict(extra="forbid")

    min_duration: int
    max_duration: int
    current_duration: int


class StructureEntity(GameEntity):
    model_config = ConfigDict(extra="forbid")

    min_duration: int
    max_duration: int
    current_duration: int


class NpcStatEntity(GameEntity):
    model_config = ConfigDict(extra="forbid")

    hp: int
    strength: int
    agility: int
    focus: int


class GameTile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: str
    tile_id: int
    x: int
    y: int


class LevelRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_id: str
    x: int
    y: int
    width: int
    height: int


class GameWorld(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_id: str
    grid_size: int
    width_px: int
    height_px: int
    entities: List[GameEntity]
    tiles: List[GameTile] = Field(default_factory=list)
    blocked_tiles: List[List[int]] = Field(default_factory=list)
    level_regions: List[LevelRegion] = Field(default_factory=list)


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
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).replace(" ", "_").replace("-", "_").lower()
    if not key:
        raise ValueError("LDtk entity key cannot be empty")

    name = str(f.get("name") or key).strip() or key
    tags = {str(tag).strip().lower() for tag in row.tags if str(tag).strip()}

    tx = int(row.px[0] // grid_size)
    ty = int(row.px[1] // grid_size)

    if "workbench" in tags or key.endswith("_workbench"):
        min_duration = max(1, int(f.get("min_duration", f.get("minDuration", 1))))
        max_duration = max(min_duration, int(f.get("max_duration", f.get("maxDuration", min_duration))))
        current_duration = int(f.get("current_duration", f.get("currentDuration", max_duration)))
        current_duration = max(min_duration, min(max_duration, current_duration))
        return WorkbenchEntity(
            key=key,
            name=name,
            x=tx,
            y=ty,
            min_duration=min_duration,
            max_duration=max_duration,
            current_duration=current_duration,
        )

    if "structure" in tags:
        min_duration = max(1, int(f.get("min_duration", f.get("minDuration", 1))))
        max_duration = max(min_duration, int(f.get("max_duration", f.get("maxDuration", min_duration))))
        current_duration = int(f.get("current_duration", f.get("currentDuration", max_duration)))
        current_duration = max(min_duration, min(max_duration, current_duration))
        return StructureEntity(
            key=key,
            name=name,
            x=tx,
            y=ty,
            min_duration=min_duration,
            max_duration=max_duration,
            current_duration=current_duration,
        )

    if "npc" in tags or key == "stat":
        hp = max(1, int(f.get("hp", 10)))
        strength = max(0, int(f.get("str", f.get("strength", 1))))
        agility = max(0, int(f.get("agi", f.get("agility", 1))))
        focus = max(0, int(f.get("foc", f.get("focus", 1))))
        return NpcStatEntity(
            key=key,
            name=name,
            x=tx,
            y=ty,
            hp=hp,
            strength=strength,
            agility=agility,
            focus=focus,
        )

    max_q = max(1, int(f.get("max_quantity", f.get("maxQuantity", 1))))
    current_q = int(f.get("current_quantity", f.get("currentQuantity", max_q)))
    current_q = max(0, min(max_q, current_q))
    is_discovered = _as_bool(f.get("is_discovered", f.get("isDiscovered", False)), False)
    return ResourceEntity(
        key=key,
        name=name,
        x=tx,
        y=ty,
        max_quantity=max_q,
        current_quantity=current_q,
        is_discovered=is_discovered,
    )


def _tiles_from_layer(layer: LdtkLayerInstance, *, fallback_grid_size: int) -> List[GameTile]:
    layer_grid = layer.grid_size or fallback_grid_size
    rows = [*layer.grid_tiles, *layer.auto_layer_tiles]
    return [
        GameTile(
            layer=layer.identifier,
            tile_id=row.tile_id,
            x=int(row.px[0] // layer_grid),
            y=int(row.px[1] // layer_grid),
        )
        for row in rows
    ]




def _offset_entity(entity: GameEntity, dx_tiles: int, dy_tiles: int) -> GameEntity:
    payload = entity.model_dump()
    payload["x"] = int(payload["x"]) + dx_tiles
    payload["y"] = int(payload["y"]) + dy_tiles
    return type(entity).model_validate(payload)


def _offset_tile(tile: GameTile, dx_tiles: int, dy_tiles: int) -> GameTile:
    payload = tile.model_dump()
    payload["x"] = int(payload["x"]) + dx_tiles
    payload["y"] = int(payload["y"]) + dy_tiles
    return GameTile.model_validate(payload)


def _build_level_world(level: LdtkLevel, project: LdtkProject, entity_layer: str) -> GameWorld:
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
    blocked_set: set[tuple[int, int]] = set()
    layer_def_by_uid = {layer.uid: layer for layer in project.defs.layers}

    for layer in layer_instances:
        if layer.layer_type == "Entities":
            continue
        tiles.extend(_tiles_from_layer(layer, fallback_grid_size=resolved_grid_size))

        if layer.identifier.lower() == "wall":
            for row in [*layer.grid_tiles, *layer.auto_layer_tiles]:
                layer_grid = layer.grid_size or resolved_grid_size
                blocked_set.add((int(row.px[0] // layer_grid), int(row.px[1] // layer_grid)))

        is_collision_layer = layer.identifier.lower() == "collision"
        value_identifiers: dict[int, str] = {}
        if layer.layer_def_uid is not None and layer.layer_def_uid in layer_def_by_uid:
            value_identifiers = {
                int(v.value): str(v.identifier or "").strip().lower()
                for v in layer_def_by_uid[layer.layer_def_uid].int_grid_values
            }
        if layer.int_grid_csv and (is_collision_layer or value_identifiers):
            cw = layer.c_wid or max(1, level.px_wid // (layer.grid_size or resolved_grid_size))
            for idx, value in enumerate(layer.int_grid_csv):
                if value == 0:
                    continue
                ident = value_identifiers.get(int(value), "")
                if is_collision_layer or "wall" in ident or "collision" in ident or "block" in ident:
                    blocked_set.add((idx % cw, idx // cw))

    return GameWorld(
        level_id=level.identifier,
        grid_size=resolved_grid_size,
        width_px=level.px_wid,
        height_px=level.px_hei,
        entities=entities,
        tiles=tiles,
        blocked_tiles=[[x, y] for x, y in sorted(blocked_set)],
        level_regions=[
            LevelRegion(
                level_id=level.identifier,
                x=0,
                y=0,
                width=max(1, int(level.px_wid // resolved_grid_size)),
                height=max(1, int(level.px_hei // resolved_grid_size)),
            )
        ],
    )

def load_ldtk_project(path: str | Path) -> LdtkProject:
    payload = orjson.loads(Path(path).read_bytes())
    return LdtkProject.model_validate(payload)


def build_world_from_ldtk(
    path: str | Path,
    *,
    level_identifier: Optional[str] = None,
    entity_layer: str = "Entities",
    merge_all_levels: bool = False,
) -> GameWorld:
    project = load_ldtk_project(path)
    if not project.levels:
        raise ValueError("LDtk project has no levels")

    if level_identifier:
        level = next((lv for lv in project.levels if lv.identifier == level_identifier), None)
        if level is None:
            raise ValueError(f"Level not found: {level_identifier}")
        return _build_level_world(level, project, entity_layer)

    if not merge_all_levels:
        return _build_level_world(project.levels[0], project, entity_layer)

    level_world_pairs = [
        (level, _build_level_world(level, project, entity_layer))
        for level in project.levels
    ]
    grid_size = max(1, min(world.grid_size for _, world in level_world_pairs))

    offset_pairs: List[tuple[LdtkLevel, GameWorld, int, int]] = []
    for level, world in level_world_pairs:
        dx_tiles = int(level.world_x // grid_size)
        dy_tiles = int(level.world_y // grid_size)
        offset_pairs.append((level, world, dx_tiles, dy_tiles))

    min_x = 0
    min_y = 0
    max_x = 0
    max_y = 0
    for level, _world, dx_tiles, dy_tiles in offset_pairs:
        level_w = max(1, int(level.px_wid // grid_size))
        level_h = max(1, int(level.px_hei // grid_size))
        min_x = min(min_x, dx_tiles)
        min_y = min(min_y, dy_tiles)
        max_x = max(max_x, dx_tiles + level_w)
        max_y = max(max_y, dy_tiles + level_h)

    shift_x = -min_x
    shift_y = -min_y

    entities: List[GameEntity] = []
    tiles: List[GameTile] = []
    blocked_set: set[tuple[int, int]] = set()
    level_regions: List[LevelRegion] = []

    for _level, world, dx_tiles, dy_tiles in offset_pairs:
        final_dx = dx_tiles + shift_x
        final_dy = dy_tiles + shift_y
        entities.extend(_offset_entity(entity, final_dx, final_dy) for entity in world.entities)
        tiles.extend(_offset_tile(tile, final_dx, final_dy) for tile in world.tiles)
        blocked_set.update((int(x) + final_dx, int(y) + final_dy) for x, y in world.blocked_tiles)
        level_regions.append(
            LevelRegion(
                level_id=_level.identifier,
                x=final_dx,
                y=final_dy,
                width=max(1, int(_level.px_wid // grid_size)),
                height=max(1, int(_level.px_hei // grid_size)),
            )
        )

    width_px = max(1, max_x - min_x) * grid_size
    height_px = max(1, max_y - min_y) * grid_size

    return GameWorld(
        level_id="ALL_LEVELS",
        grid_size=grid_size,
        width_px=width_px,
        height_px=height_px,
        entities=entities,
        tiles=tiles,
        blocked_tiles=[[x, y] for x, y in sorted(blocked_set)],
        level_regions=level_regions,
    )


def world_entities_as_rows(world: GameWorld) -> List[Dict[str, object]]:
    return [entity.model_dump() for entity in world.entities]


def world_tiles_as_rows(world: GameWorld) -> List[Dict[str, object]]:
    return [tile.model_dump() for tile in world.tiles]
