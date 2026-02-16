#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Arcade runtime for LDtk world data.

Usage:
    python arcade_ldtk_game.py --ldtk path/to/world.ldtk [--level Level_0]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Optional

import arcade

from ldtk_integration import GameEntity, GameWorld, build_world_from_ldtk


@dataclass
class CameraState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


@dataclass
class SimulationState:
    tick_seconds: float = 1.0
    running: bool = False
    tick_count: int = 0
    accumulator: float = 0.0
    selected_index: Optional[int] = None
    logs: list[str] = field(default_factory=list)

    def add_log(self, message: str) -> None:
        self.logs.append(message)
        if len(self.logs) > 8:
            self.logs = self.logs[-8:]

    def update(self, dt: float) -> int:
        if not self.running:
            return 0
        self.accumulator += max(0.0, dt)
        ticks = 0
        while self.accumulator >= self.tick_seconds:
            self.accumulator -= self.tick_seconds
            self.tick_count += 1
            ticks += 1
        return ticks


class LdtkArcadeWindow(arcade.Window):
    def __init__(self, world: GameWorld):
        super().__init__(1280, 720, f"Arcade + LDtk | {world.level_id}", resizable=True)
        self.world = world
        self.camera = arcade.Camera2D(position=(0, 0), zoom=1.0)
        self.state = CameraState()
        self.sim = SimulationState()
        self.move_speed = 500.0

    def _entity_color(self, entity: GameEntity, idx: int) -> tuple[int, int, int, int]:
        if self.sim.selected_index == idx:
            return 255, 216, 120, 255
        if entity.is_workbench:
            return 198, 140, 80, 255
        if not entity.is_discovered:
            return 90, 110, 90, 255
        return 90, 170, 120, 255

    def _entity_world_pos(self, entity: GameEntity) -> tuple[float, float]:
        tile = self.world.grid_size
        return entity.x * tile + tile / 2, entity.y * tile + tile / 2

    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        wx = (sx - self.width / 2) / self.state.zoom + self.state.x
        wy = (sy - self.height / 2) / self.state.zoom + self.state.y
        return wx, wy

    def _pick_entity(self, sx: float, sy: float) -> Optional[int]:
        wx, wy = self._screen_to_world(sx, sy)
        tile = self.world.grid_size
        radius = max(8.0, tile * 0.55)
        best_idx: Optional[int] = None
        best_dist = float("inf")

        for idx, entity in enumerate(self.world.entities):
            ex, ey = self._entity_world_pos(entity)
            dist = ((ex - wx) ** 2 + (ey - wy) ** 2) ** 0.5
            if dist <= radius and dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx

    def _selected_entity(self) -> Optional[GameEntity]:
        if self.sim.selected_index is None:
            return None
        if not (0 <= self.sim.selected_index < len(self.world.entities)):
            return None
        return self.world.entities[self.sim.selected_index]

    def _interact_selected(self) -> None:
        entity = self._selected_entity()
        if entity is None:
            self.sim.add_log("[interact] 선택된 엔티티가 없습니다.")
            return

        if entity.is_workbench:
            entity.is_discovered = True
            self.sim.add_log(f"[interact] {entity.name}: 작업대 확인")
            return

        if entity.current_quantity <= 0:
            self.sim.add_log(f"[interact] {entity.name}: 수량이 없습니다")
            return

        entity.is_discovered = True
        entity.current_quantity = max(0, entity.current_quantity - 1)
        self.sim.add_log(f"[interact] {entity.name}: 수집 성공 (남은 수량 {entity.current_quantity})")

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

        advanced = self.sim.update(delta_time)
        if advanced > 0:
            self.sim.add_log(f"[tick] +{advanced} (total={self.sim.tick_count})")

    def on_draw(self):
        self.clear((25, 28, 32, 255))
        with self.camera.activate():
            arcade.draw_lrbt_rectangle_filled(0, self.world.width_px, 0, self.world.height_px, (38, 42, 50, 255))

            tile = self.world.grid_size
            for y in range(0, self.world.height_px, tile):
                arcade.draw_line(0, y, self.world.width_px, y, (46, 52, 60, 80), 1)
            for x in range(0, self.world.width_px, tile):
                arcade.draw_line(x, 0, x, self.world.height_px, (46, 52, 60, 80), 1)

            for idx, entity in enumerate(self.world.entities):
                ex, ey = self._entity_world_pos(entity)
                arcade.draw_circle_filled(ex, ey, max(4, tile * 0.28), self._entity_color(entity, idx))
                arcade.draw_text(entity.name, ex + 6, ey + 6, (230, 230, 230, 255), 10)

        selected = self._selected_entity()
        selected_label = "없음" if selected is None else f"{selected.name} ({selected.key}) q={selected.current_quantity}"
        status = "RUN" if self.sim.running else "PAUSE"

        arcade.draw_text(
            "WASD/Arrow: move | Wheel: zoom | Space: pause/resume tick | Click: select | E: interact",
            12,
            self.height - 24,
            (220, 220, 220, 255),
            12,
        )
        arcade.draw_text(
            f"Tick={self.sim.tick_count} | State={status} | Selected={selected_label}",
            12,
            self.height - 46,
            (235, 235, 235, 255),
            12,
        )

        y = self.height - 70
        arcade.draw_text("Logs:", 12, y, (200, 200, 180, 255), 11)
        for line in reversed(self.sim.logs[-6:]):
            y -= 16
            arcade.draw_text(line, 12, y, (210, 210, 210, 255), 11)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int):
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        idx = self._pick_entity(x, y)
        self.sim.selected_index = idx
        if idx is None:
            self.sim.add_log("[select] 선택 해제")
        else:
            ent = self.world.entities[idx]
            self.sim.add_log(f"[select] {ent.name} ({ent.key})")

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if scroll_y > 0:
            self.state.zoom = min(3.0, self.state.zoom * 1.08)
        elif scroll_y < 0:
            self.state.zoom = max(0.4, self.state.zoom / 1.08)
        self.camera.zoom = self.state.zoom

    def on_key_press(self, key: int, modifiers: int):
        self._keys[key] = True
        if key == arcade.key.SPACE:
            self.sim.running = not self.sim.running
            self.sim.add_log(f"[sim] {'재개' if self.sim.running else '일시정지'}")
        elif key == arcade.key.E:
            self._interact_selected()

    def on_key_release(self, key: int, modifiers: int):
        self._keys[key] = False

    def setup(self):
        self._keys: dict[int, bool] = {}
        self.state = CameraState(
            x=self.world.width_px / 2,
            y=self.world.height_px / 2,
            zoom=1.0,
        )
        self.sim = SimulationState(running=False, tick_seconds=1.0)
        self.sim.add_log("[boot] SPACE로 시뮬레이션 시작")
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
