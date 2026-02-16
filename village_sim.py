#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Arcade-first village simulator runtime.

이 모듈은 기존 pygame 루프를 폐기하고 아래 스택으로 단순화했다.
- rendering/runtime: arcade
- world source: LDtk(optional) + data/entities.json
- schema validation: pydantic
- JSON I/O: orjson
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from editable_data import DATA_DIR, load_entities
from ldtk_integration import GameEntity, GameWorld, build_world_from_ldtk


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_width: int = 1280
    window_height: int = 720
    title: str = "Arcade Village Sim"
    camera_speed: float = 520.0
    zoom_min: float = 0.4
    zoom_max: float = 3.0
    zoom_in_step: float = 1.08
    zoom_out_step: float = 0.92


class CameraState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


class JsonEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str
    name: str
    x: int
    y: int
    max_quantity: int = Field(default=1, ge=1)
    current_quantity: int = Field(default=0, ge=0)
    is_workbench: bool = False
    is_discovered: bool = False


class JsonNpc(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    job: str = "농부"
    x: int | None = None
    y: int | None = None


class RenderNpc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    job: str
    x: int
    y: int


def world_from_entities_json(level_id: str = "json_world", grid_size: int = 16) -> GameWorld:
    entities = [JsonEntity.model_validate(row) for row in load_entities()]
    if not entities:
        raise ValueError("entities.json has no entities")

    max_x = max(e.x for e in entities) + 1
    max_y = max(e.y for e in entities) + 1

    game_entities: List[GameEntity] = [
        GameEntity(
            key=e.key,
            name=e.name,
            x=e.x,
            y=e.y,
            max_quantity=e.max_quantity,
            current_quantity=min(e.max_quantity, e.current_quantity),
            is_workbench=e.is_workbench,
            is_discovered=True if e.is_workbench else e.is_discovered,
        )
        for e in entities
    ]

    return GameWorld(
        level_id=level_id,
        grid_size=grid_size,
        width_px=max_x * grid_size,
        height_px=max_y * grid_size,
        entities=game_entities,
    )




def _stable_layer_color(layer_name: str) -> tuple[int, int, int, int]:
    seed = sum(ord(ch) for ch in layer_name)
    r = 40 + (seed * 37) % 120
    g = 50 + (seed * 57) % 120
    b = 60 + (seed * 79) % 120
    return int(r), int(g), int(b), 130

def run_arcade(world: GameWorld, config: RuntimeConfig) -> None:
    import arcade

    npcs = _build_render_npcs(world)

    class VillageArcadeWindow(arcade.Window):
        def __init__(self):
            super().__init__(config.window_width, config.window_height, config.title, resizable=True)
            self.camera = arcade.Camera2D(position=(0, 0), zoom=1.0)
            self.state = CameraState(x=world.width_px / 2, y=world.height_px / 2, zoom=1.0)
            self._keys: dict[int, bool] = {}

        @staticmethod
        def _entity_color(entity: GameEntity) -> tuple[int, int, int, int]:
            if entity.is_workbench:
                return 198, 140, 80, 255
            if not entity.is_discovered:
                return 95, 108, 95, 255
            return 86, 176, 132, 255

        def on_update(self, delta_time: float):
            dx = dy = 0.0
            if self._keys.get(arcade.key.A) or self._keys.get(arcade.key.LEFT):
                dx -= 1.0
            if self._keys.get(arcade.key.D) or self._keys.get(arcade.key.RIGHT):
                dx += 1.0
            if self._keys.get(arcade.key.W) or self._keys.get(arcade.key.UP):
                dy += 1.0
            if self._keys.get(arcade.key.S) or self._keys.get(arcade.key.DOWN):
                dy -= 1.0
            if dx == 0 and dy == 0:
                return
            magnitude = (dx * dx + dy * dy) ** 0.5
            self.state.x += (dx / magnitude) * config.camera_speed * delta_time
            self.state.y += (dy / magnitude) * config.camera_speed * delta_time
            self.camera.position = (self.state.x, self.state.y)

        def on_key_press(self, key: int, modifiers: int):
            self._keys[key] = True
            if key == arcade.key.Q:
                self.state.zoom = max(config.zoom_min, self.state.zoom * config.zoom_out_step)
                self.camera.zoom = self.state.zoom
            elif key == arcade.key.E:
                self.state.zoom = min(config.zoom_max, self.state.zoom * config.zoom_in_step)
                self.camera.zoom = self.state.zoom

        def on_key_release(self, key: int, modifiers: int):
            self._keys[key] = False

        def on_draw(self):
            self.clear((25, 28, 32, 255))
            tile = world.grid_size
            with self.camera.activate():
                arcade.draw_lrbt_rectangle_filled(0, world.width_px, 0, world.height_px, (38, 42, 50, 255))

                for tile_row in world.tiles:
                    tx = tile_row.x * tile
                    ty = tile_row.y * tile
                    arcade.draw_lrbt_rectangle_filled(
                        tx,
                        tx + tile,
                        ty,
                        ty + tile,
                        _stable_layer_color(tile_row.name),
                    )

                for y in range(0, world.height_px, tile):
                    arcade.draw_line(0, y, world.width_px, y, (46, 52, 60, 80), 1)
                for x in range(0, world.width_px, tile):
                    arcade.draw_line(x, 0, x, world.height_px, (46, 52, 60, 80), 1)

                for npc in npcs:
                    nx = npc.x * tile + tile / 2
                    ny = npc.y * tile + tile / 2
                    arcade.draw_circle_filled(nx, ny, max(4, tile * 0.24), _npc_color(npc.job))
                    arcade.draw_text(npc.name, nx + 5, ny - 12, (240, 240, 240, 255), 9)

                for entity in world.entities:
                    ex = entity.x * tile + tile / 2
                    ey = entity.y * tile + tile / 2
                    arcade.draw_circle_filled(ex, ey, max(4, tile * 0.28), self._entity_color(entity))
                    arcade.draw_text(entity.name, ex + 6, ey + 6, (230, 230, 230, 255), 10)

            arcade.draw_text("WASD/Arrow: move | Q/E: zoom", 12, self.height - 24, (220, 220, 220, 255), 12)

    VillageArcadeWindow()
    arcade.run()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Arcade village simulator runner")
    default_ldtk = DATA_DIR / "map.ldtk"
    parser.add_argument("--ldtk", default=str(default_ldtk), help=f"Path to LDtk project (default: {default_ldtk})")
    parser.add_argument("--level", default=None, help="LDtk level identifier")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = RuntimeConfig()
    world = build_world_from_ldtk(Path(args.ldtk), level_identifier=args.level)
    run_arcade(world, config)


if __name__ == "__main__":
    main()
