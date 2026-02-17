#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Arcade runtime for LDtk world data.

Usage:
    python arcade_ldtk_game.py --ldtk path/to/world.ldtk [--level Level_0]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import arcade

from ldtk_integration import GameEntity, GameWorld, WorkbenchEntity, build_world_from_ldtk

def _has_workbench_trait(entity: GameEntity) -> bool:
    return isinstance(entity, WorkbenchEntity) or entity.key.strip().lower().endswith("_workbench")


@dataclass
class CameraState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


class LdtkArcadeWindow(arcade.Window):
    def __init__(self, world: GameWorld):
        super().__init__(1280, 720, f"Arcade + LDtk | {world.level_id}", resizable=True)
        self.world = world
        self.camera = arcade.Camera2D(position=(0, 0), zoom=1.0)
        self.state = CameraState()
        self.move_speed = 500.0

    def _entity_color(self, entity: GameEntity) -> tuple[int, int, int, int]:
        if _has_workbench_trait(entity):
            return 198, 140, 80, 255
        return 112, 120, 156, 255

    def _entity_world_pos(self, entity: GameEntity) -> tuple[float, float]:
        tile = self.world.grid_size
        return entity.x * tile + tile / 2, entity.y * tile + tile / 2

    def on_update(self, delta_time: float):
        dx = dy = 0.0
        if self._keys.get(arcade.key.A) or self._keys.get(arcade.key.LEFT):
            dx -= 1
        if self._keys.get(arcade.key.D) or self._keys.get(arcade.key.RIGHT):
            dx += 1
        if self._keys.get(arcade.key.W) or self._keys.get(arcade.key.UP):
            dy += 1
        if self._keys.get(arcade.key.S) or self._keys.get(arcade.key.DOWN):
            dy -= 1

        if dx != 0 or dy != 0:
            mag = (dx * dx + dy * dy) ** 0.5
            dx /= mag
            dy /= mag
            self.state.x += dx * self.move_speed * delta_time
            self.state.y += dy * self.move_speed * delta_time
            self.camera.position = (self.state.x, self.state.y)

    def on_draw(self):
        self.clear((25, 28, 32, 255))
        with self.camera.activate():
            arcade.draw_lrbt_rectangle_filled(0, self.world.width_px, 0, self.world.height_px, (38, 42, 50, 255))

            tile = self.world.grid_size
            for world_tile in self.world.tiles:
                tx = world_tile.x * tile
                ty = world_tile.y * tile
                layer_name = world_tile.layer.strip().lower()
                if layer_name == "road":
                    color = (95, 126, 162, 255)
                elif layer_name == "wall":
                    color = (116, 96, 86, 255)
                else:
                    shade = 72 + (world_tile.tile_id % 5) * 18
                    color = (shade, min(255, shade + 20), min(255, shade + 38), 255)
                arcade.draw_lrbt_rectangle_filled(tx, tx + tile, ty, ty + tile, color)

            for x, y in self.world.blocked_tiles:
                bx = int(x) * tile
                by = int(y) * tile
                arcade.draw_lrbt_rectangle_filled(bx, bx + tile, by, by + tile, (120, 68, 68, 110))

            for y in range(0, self.world.height_px, tile):
                arcade.draw_line(0, y, self.world.width_px, y, (46, 52, 60, 80), 1)
            for x in range(0, self.world.width_px, tile):
                arcade.draw_line(x, 0, x, self.world.height_px, (46, 52, 60, 80), 1)

            for entity in self.world.entities:
                ex, ey = self._entity_world_pos(entity)
                arcade.draw_circle_filled(ex, ey, max(4, tile * 0.28), self._entity_color(entity))
                arcade.draw_text(entity.name, ex + 6, ey + 6, (230, 230, 230, 255), 10)

        arcade.draw_text(
            "WASD/Arrow: move | Q/E: zoom",
            12,
            self.height - 24,
            (220, 220, 220, 255),
            12,
        )
        arcade.draw_text(
            f"level={self.world.level_id} tiles={len(self.world.tiles)} blocked={len(self.world.blocked_tiles)} entities={len(self.world.entities)}",
            12,
            self.height - 44,
            (232, 232, 232, 255),
            11,
        )

    def on_key_press(self, key: int, modifiers: int):
        self._keys[key] = True
        if key == arcade.key.Q:
            self.state.zoom = max(0.4, self.state.zoom * 0.92)
            self.camera.zoom = self.state.zoom
        elif key == arcade.key.E:
            self.state.zoom = min(3.0, self.state.zoom * 1.08)
            self.camera.zoom = self.state.zoom

    def on_key_release(self, key: int, modifiers: int):
        self._keys[key] = False

    def setup(self):
        self._keys: dict[int, bool] = {}
        self.state = CameraState(
            x=self.world.width_px / 2,
            y=self.world.height_px / 2,
            zoom=1.0,
        )
        self.camera.position = (self.state.x, self.state.y)
        self.camera.zoom = self.state.zoom


def main():
    parser = argparse.ArgumentParser(description="Arcade + LDtk game runner")
    default_ldtk = Path(__file__).resolve().parent / "data" / "map.ldtk"
    parser.add_argument("--ldtk", default=str(default_ldtk), help=f"Path to LDtk project file (default: {default_ldtk})")
    parser.add_argument("--level", default=None, help="Level identifier")
    args = parser.parse_args()

    world = build_world_from_ldtk(
        args.ldtk,
        level_identifier=args.level,
        merge_all_levels=args.level is None,
    )
    print(
        f"[LDTK] level={world.level_id} size={world.width_px}x{world.height_px} "
        f"tiles={len(world.tiles)} blocked={len(world.blocked_tiles)} entities={len(world.entities)}"
    )
    window = LdtkArcadeWindow(world)
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()
