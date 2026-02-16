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
from random import Random
from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field

from editable_data import (
    DATA_DIR,
    load_action_defs,
    load_entities,
    load_job_defs,
    load_npc_templates,
)
from ldtk_integration import GameEntity, GameWorld, build_world_from_ldtk
from planning import DailyPlanner, ScheduledActivity


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


class SimulationNpcState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_action: str = "대기"
    ticks_remaining: int = 0


class SimulationRuntime:
    """렌더 루프와 분리된 고정 틱(10분 단위) 시뮬레이터."""

    TICK_MINUTES = 10
    TICKS_PER_HOUR = 60 // TICK_MINUTES

    def __init__(
        self,
        world: GameWorld,
        npcs: List[RenderNpc],
        tick_seconds: float = 0.25,
        seed: int = 42,
        start_hour: int = 8,
    ):
        self.world = world
        self.npcs = npcs
        self.tick_seconds = max(0.05, float(tick_seconds))
        self._accumulator = 0.0
        self.ticks = 0
        self.rng = Random(seed)
        self.start_hour = int(start_hour) % 24
        self.planner = DailyPlanner()

        self.job_actions = self._job_actions_map()
        self.action_duration_ticks = self._action_duration_map()
        self.state_by_name: Dict[str, SimulationNpcState] = {
            npc.name: SimulationNpcState() for npc in self.npcs
        }

    @staticmethod
    def _duration_to_ticks(minutes: object) -> int:
        try:
            parsed = int(minutes)
        except Exception:
            parsed = 10
        return max(1, parsed // 10)

    def _job_actions_map(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for row in load_job_defs():
            if not isinstance(row, dict):
                continue
            job = str(row.get("job", "")).strip()
            if not job:
                continue
            actions = [str(x).strip() for x in row.get("work_actions", []) if str(x).strip()]
            if actions:
                out[job] = actions
        return out

    def _action_duration_map(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for row in load_action_defs():
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            out[name] = self._duration_to_ticks(row.get("duration_minutes", 10))
        return out

    def _current_hour(self) -> int:
        hours_elapsed = self.ticks // self.TICKS_PER_HOUR
        return (self.start_hour + hours_elapsed) % 24

    def _pick_next_action(self, npc: RenderNpc, state: SimulationNpcState) -> None:
        activity = self.planner.activity_for_hour(self._current_hour())
        if activity == ScheduledActivity.MEAL:
            state.current_action = "식사"
            state.ticks_remaining = self.TICKS_PER_HOUR
            return
        if activity == ScheduledActivity.SLEEP:
            state.current_action = "취침"
            state.ticks_remaining = self.TICKS_PER_HOUR
            return

        candidates = self.job_actions.get(npc.job, [])
        if not candidates:
            state.current_action = "배회"
            state.ticks_remaining = 1
            return
        action = self.rng.choice(candidates)
        state.current_action = action
        state.ticks_remaining = self.action_duration_ticks.get(action, 1)

    def _step_npc(self, npc: RenderNpc) -> None:
        state = self.state_by_name[npc.name]
        if state.ticks_remaining <= 0:
            self._pick_next_action(npc, state)

        state.ticks_remaining = max(0, state.ticks_remaining - 1)

        width_tiles = max(1, self.world.width_px // self.world.grid_size)
        height_tiles = max(1, self.world.height_px // self.world.grid_size)
        dx, dy = self.rng.choice([(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)])
        npc.x = min(max(0, npc.x + dx), width_tiles - 1)
        npc.y = min(max(0, npc.y + dy), height_tiles - 1)

    def tick_once(self) -> None:
        self.ticks += 1
        for npc in self.npcs:
            self._step_npc(npc)

    def advance(self, delta_time: float) -> None:
        self._accumulator += max(0.0, float(delta_time))
        while self._accumulator >= self.tick_seconds:
            self._accumulator -= self.tick_seconds
            self.tick_once()

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


def _npc_color(job_name: str) -> tuple[int, int, int, int]:
    seed = sum(ord(ch) for ch in job_name)
    r = 140 + (seed * 17) % 95
    g = 120 + (seed * 29) % 110
    b = 130 + (seed * 43) % 95
    return int(r), int(g), int(b), 255


FONT_CANDIDATES: tuple[str, ...] = (
    "Noto Sans CJK KR",
    "Noto Sans KR",
    "NanumGothic",
    "NanumBarunGothic",
    "NanumSquare",
    "Arial Unicode MS",
    "sans-serif",
)


def _pick_font_name() -> str:
    """설치된 폰트 후보 중 첫 번째를 선택한다."""

    try:
        import pyglet

        for name in FONT_CANDIDATES:
            if pyglet.font.have_font(name):
                return name
    except Exception:
        pass
    return FONT_CANDIDATES[0]


def _build_render_npcs(world: GameWorld) -> List[RenderNpc]:
    raw_npcs = [JsonNpc.model_validate(row) for row in load_npc_templates() if isinstance(row, dict)]
    if not raw_npcs:
        return []

    width_tiles = max(1, world.width_px // world.grid_size)
    height_tiles = max(1, world.height_px // world.grid_size)

    out: List[RenderNpc] = []
    for idx, npc in enumerate(raw_npcs):
        default_x = 1 + (idx % max(1, width_tiles - 2))
        default_y = 1 + ((idx // max(1, width_tiles - 2)) % max(1, height_tiles - 2))
        x = npc.x if npc.x is not None else default_x
        y = npc.y if npc.y is not None else default_y
        x = min(max(0, int(x)), width_tiles - 1)
        y = min(max(0, int(y)), height_tiles - 1)
        out.append(RenderNpc(name=npc.name, job=npc.job, x=x, y=y))
    return out


def run_arcade(world: GameWorld, config: RuntimeConfig) -> None:
    import arcade

    npcs = _build_render_npcs(world)
    simulation = SimulationRuntime(world, npcs)
    selected_font = _pick_font_name()

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
            if dx != 0 or dy != 0:
                magnitude = (dx * dx + dy * dy) ** 0.5
                self.state.x += (dx / magnitude) * config.camera_speed * delta_time
                self.state.y += (dy / magnitude) * config.camera_speed * delta_time
                self.camera.position = (self.state.x, self.state.y)
            simulation.advance(delta_time)

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
                        _stable_layer_color(tile_row.layer),
                    )

                for y in range(0, world.height_px, tile):
                    arcade.draw_line(0, y, world.width_px, y, (46, 52, 60, 80), 1)
                for x in range(0, world.width_px, tile):
                    arcade.draw_line(x, 0, x, world.height_px, (46, 52, 60, 80), 1)

                for npc in npcs:
                    nx = npc.x * tile + tile / 2
                    ny = npc.y * tile + tile / 2
                    arcade.draw_circle_filled(nx, ny, max(4, tile * 0.24), _npc_color(npc.job))
                    sim_state = simulation.state_by_name.get(npc.name)
                    label = npc.name if sim_state is None else f"{npc.name}({sim_state.current_action})"
                    arcade.draw_text(label, nx + 5, ny - 12, (240, 240, 240, 255), 9, font_name=selected_font)

                for entity in world.entities:
                    ex = entity.x * tile + tile / 2
                    ey = entity.y * tile + tile / 2
                    arcade.draw_circle_filled(ex, ey, max(4, tile * 0.28), self._entity_color(entity))
                    arcade.draw_text(entity.name, ex + 6, ey + 6, (230, 230, 230, 255), 10, font_name=selected_font)

            hud = f"WASD/Arrow: move | Q/E: zoom | sim_tick={simulation.ticks}"
            arcade.draw_text(hud, 12, self.height - 24, (220, 220, 220, 255), 12, font_name=selected_font)

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
