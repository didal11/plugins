#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Arcade runtime for LDtk world data.

Usage:
    python arcade_ldtk_game.py --ldtk path/to/world.ldtk [--level Level_0]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import arcade

from ldtk_integration import GameEntity, GameWorld, build_world_from_ldtk


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
        if entity.is_workbench:
            return 198, 140, 80, 255
        if not entity.is_discovered:
            return 90, 110, 90, 255
        return 90, 170, 120, 255

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
    parser.add_argument("--ldtk", required=True, help="Path to LDtk project file")
    parser.add_argument("--level", default=None, help="Level identifier")
    args = parser.parse_args()

    world = build_world_from_ldtk(args.ldtk, level_identifier=args.level)
    window = LdtkArcadeWindow(world)
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()
