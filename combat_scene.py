#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""격자 맵 기반 전투 씬 프로토타입 (아케이드 전용 실행)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import random
from typing import Dict, List, Optional, Sequence

try:
    import arcade
except ImportError:  # optional dependency
    arcade = None


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


@dataclass(frozen=True)
class ActionDefinition:
    key: str
    label: str
    tick_cost: int


@dataclass
class Combatant:
    name: str
    team: str
    hp: int
    attack: int
    agility: int
    x: int
    y: int
    next_action_tick: int = 0
    cooldown_total: int = 1
    alive: bool = True
    icon: str = "?"
    last_action: str = "대기"

    def schedule_next(self, tick_cost: int, now_tick: int) -> None:
        delay = max(1, tick_cost)
        base = max(self.next_action_tick, now_tick)
        self.next_action_tick = base + delay
        self.cooldown_total = delay


@dataclass
class CombatSceneEngine:
    actors: List[Combatant]
    action_defs: Dict[str, ActionDefinition]
    map_width: int = 14
    map_height: int = 8
    rng: random.Random = field(default_factory=random.Random)
    current_tick: int = 0
    log: List[str] = field(default_factory=list)

    def ready_combatants(self) -> List[Combatant]:
        ready = [x for x in self.actors if x.alive and x.next_action_tick <= self.current_tick]
        ready.sort(key=lambda x: (-x.agility, x.name))
        return ready

    def alive_enemies(self, actor: Combatant) -> List[Combatant]:
        return [x for x in self.actors if x.alive and x.team != actor.team]

    def is_battle_over(self) -> bool:
        alive_teams = {x.team for x in self.actors if x.alive}
        return len(alive_teams) <= 1

    def winner_team(self) -> Optional[str]:
        alive_teams = {x.team for x in self.actors if x.alive}
        if len(alive_teams) != 1:
            return None
        return next(iter(alive_teams))

    @staticmethod
    def _manhattan(a: Combatant, b: Combatant) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)

    def choose_npc_action(self, actor: Combatant, enemies: Sequence[Combatant]) -> str:
        nearest = min(self._manhattan(actor, x) for x in enemies)
        if nearest <= 1:
            return "attack"
        if actor.agility >= 7:
            return "move"
        return "attack" if self.rng.random() < 0.35 else "move"

    def execute_action(self, actor: Combatant, action_key: str) -> None:
        enemies = self.alive_enemies(actor)
        if not enemies or not actor.alive:
            return

        if action_key == "move":
            self._execute_move(actor, enemies)
            actor.schedule_next(self.action_defs["move"].tick_cost, self.current_tick)
            return

        target = min(enemies, key=lambda x: self._manhattan(actor, x))
        self._execute_attack(actor, target)
        actor.schedule_next(self.action_defs["attack"].tick_cost, self.current_tick)

    def advance_tick(self) -> None:
        self.current_tick += 1

    def _execute_move(self, actor: Combatant, enemies: Sequence[Combatant]) -> None:
        target = min(enemies, key=lambda x: self._manhattan(actor, x))
        before = (actor.x, actor.y)
        candidates: list[tuple[int, int]] = []
        if actor.x < target.x:
            candidates.append((actor.x + 1, actor.y))
        elif actor.x > target.x:
            candidates.append((actor.x - 1, actor.y))

        if actor.y < target.y:
            candidates.append((actor.x, actor.y + 1))
        elif actor.y > target.y:
            candidates.append((actor.x, actor.y - 1))

        if not candidates:
            candidates.append((actor.x, actor.y))

        occupied = {(x.x, x.y) for x in self.actors if x.alive and x.name != actor.name}
        moved = False
        for nx, ny in candidates:
            if 0 <= nx < self.map_width and 0 <= ny < self.map_height and (nx, ny) not in occupied:
                actor.x = nx
                actor.y = ny
                moved = True
                break

        actor.last_action = self.action_defs["move"].label
        if moved:
            self.log.append(
                f"[T{self.current_tick:03}] {actor.name} 이동 {before}->{(actor.x, actor.y)} (+{self.action_defs['move'].tick_cost}틱)"
            )
        else:
            self.log.append(f"[T{self.current_tick:03}] {actor.name} 이동 시도(막힘)")

    def _execute_attack(self, actor: Combatant, target: Combatant) -> None:
        if self._manhattan(actor, target) > 1:
            actor.last_action = self.action_defs["attack"].label
            self.log.append(f"[T{self.current_tick:03}] {actor.name} -> {target.name} 공격 실패(사거리 밖)")
            return

        hit_chance = max(0.15, min(0.95, 0.72 + (actor.agility - target.agility) * 0.03))
        if self.rng.random() > hit_chance:
            actor.last_action = self.action_defs["attack"].label
            self.log.append(f"[T{self.current_tick:03}] {actor.name} -> {target.name} 공격 빗나감")
            return

        variance = self.rng.randint(-2, 3)
        damage = max(1, actor.attack + variance)
        before_hp = target.hp
        target.hp = max(0, target.hp - damage)
        target.alive = target.hp > 0
        actor.last_action = self.action_defs["attack"].label
        down = " (전투불능)" if not target.alive else ""
        self.log.append(
            f"[T{self.current_tick:03}] {actor.name} -> {target.name} {before_hp}->{target.hp} dmg:{damage}{down}"
        )


class CombatSceneArcadeWindow(arcade.Window if arcade else object):
    def __init__(self, engine: CombatSceneEngine, tick_seconds: float = 1.0):
        if arcade is None:
            raise RuntimeError("arcade 패키지가 설치되어 있지 않습니다.")
        super().__init__(1200, 760, "Combat Scene (Grid Map, Real-time Click)")
        self.engine = engine
        self.tick_seconds = max(0.05, float(tick_seconds))
        self._acc = 0.0
        self.selected_font = _pick_font_name()

        self._battle_done = False
        self._selected_player_name: Optional[str] = None
        self._player_action_mode: Dict[str, str] = {
            actor.name: "attack" for actor in self.engine.actors if actor.team == "player"
        }

        self.grid_origin_x = 40
        self.grid_origin_y = 140
        self.tile_px = 70

        self.attack_btn = arcade.LRBT(left=860, right=1140, bottom=150, top=220)
        self.move_btn = arcade.LRBT(left=860, right=1140, bottom=60, top=130)

    def _tile_center(self, x: int, y: int) -> tuple[float, float]:
        return (
            self.grid_origin_x + x * self.tile_px + self.tile_px / 2,
            self.grid_origin_y + y * self.tile_px + self.tile_px / 2,
        )

    def _cooldown_boxes(self, actor: Combatant, width: int = 5) -> str:
        total = max(1, actor.cooldown_total)
        remaining = max(0, actor.next_action_tick - self.engine.current_tick)
        progressed = max(0, min(total, total - remaining))
        filled = int(round((progressed / total) * width))
        return "■" * filled + "□" * (width - filled)

    def on_draw(self) -> None:
        self.clear((18, 20, 26))

        arcade.draw_text(
            f"TICK {self.engine.current_tick:03}",
            40,
            720,
            arcade.color.LIGHT_GRAY,
            20,
            font_name=self.selected_font,
        )
        arcade.draw_text(
            "격자 전투 맵",
            40,
            692,
            arcade.color.ASH_GREY,
            14,
            font_name=self.selected_font,
        )

        left = self.grid_origin_x
        bottom = self.grid_origin_y
        right = left + self.engine.map_width * self.tile_px
        top = bottom + self.engine.map_height * self.tile_px
        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, (30, 35, 45, 255))

        for y in range(self.engine.map_height + 1):
            py = bottom + y * self.tile_px
            arcade.draw_line(left, py, right, py, (70, 78, 92, 130), 1)
        for x in range(self.engine.map_width + 1):
            px = left + x * self.tile_px
            arcade.draw_line(px, bottom, px, top, (70, 78, 92, 130), 1)

        for actor in self.engine.actors:
            if not actor.alive:
                continue
            cx, cy = self._tile_center(actor.x, actor.y)
            is_selected = actor.name == self._selected_player_name
            body = arcade.color.BRIGHT_NAVY_BLUE if actor.team == "player" else arcade.color.DARK_PASTEL_RED
            if is_selected:
                arcade.draw_circle_outline(cx, cy, self.tile_px * 0.40, arcade.color.YELLOW, 4)
            arcade.draw_circle_filled(cx, cy, self.tile_px * 0.30, body)
            arcade.draw_text(actor.icon, cx, cy - 8, arcade.color.WHITE, 18, anchor_x="center", font_name=self.selected_font)
            arcade.draw_text(
                self._cooldown_boxes(actor),
                cx,
                cy + self.tile_px * 0.36,
                arcade.color.LIGHT_GRAY,
                11,
                anchor_x="center",
                font_name=self.selected_font,
            )

        y = 640
        arcade.draw_text("상태", 860, y, arcade.color.WHITE, 16, font_name=self.selected_font)
        y -= 26
        for actor in sorted(self.engine.actors, key=lambda x: (x.team, x.name)):
            state = "DOWN" if not actor.alive else f"HP:{actor.hp:02} ({actor.x},{actor.y})"
            mode = self._player_action_mode.get(actor.name, "-") if actor.team == "player" else "AI"
            row = f"{actor.icon} {actor.name:<8} [{actor.team}] {state} 모드:{mode}"
            color = arcade.color.LIGHT_GRAY if actor.alive else arcade.color.DARK_GRAY
            arcade.draw_text(row, 860, y, color, 12, font_name=self.selected_font)
            y -= 20

        arcade.draw_text("최근 로그", 40, 92, arcade.color.WHITE, 15, font_name=self.selected_font)
        log_y = 68
        for row in self.engine.log[-4:]:
            arcade.draw_text(row, 40, log_y, arcade.color.ASH_GREY, 12, font_name=self.selected_font)
            log_y -= 18

        selected = self._selected_player_name
        attack_active = bool(selected and self._player_action_mode.get(selected) == "attack")
        move_active = bool(selected and self._player_action_mode.get(selected) == "move")

        attack_color = arcade.color.DARK_SPRING_GREEN if attack_active else arcade.color.DARK_SLATE_GRAY
        move_color = arcade.color.INDIGO if move_active else arcade.color.DARK_SLATE_GRAY
        arcade.draw_lrbt_rectangle_filled(*self._rect_points(self.attack_btn), attack_color)
        arcade.draw_lrbt_rectangle_filled(*self._rect_points(self.move_btn), move_color)
        arcade.draw_text("공격 모드", 1000, 178, arcade.color.WHITE, 18, anchor_x="center", font_name=self.selected_font)
        arcade.draw_text("이동 모드", 1000, 88, arcade.color.WHITE, 18, anchor_x="center", font_name=self.selected_font)

        if self._battle_done:
            winner = self.engine.winner_team()
            msg = f"전투 종료 - 승리 팀: {winner}" if winner else "전투 종료 - 무승부"
            arcade.draw_text(msg, 860, 20, arcade.color.YELLOW, 18, font_name=self.selected_font)
        elif selected:
            msg = f"선택: {selected} / 클릭으로 모드 변경(실시간 진행)"
            arcade.draw_text(msg, 860, 20, arcade.color.YELLOW, 14, font_name=self.selected_font)
        else:
            arcade.draw_text("플레이어 NPC를 클릭해 행동 모드를 선택하세요", 860, 20, arcade.color.LIGHT_GRAY, 14, font_name=self.selected_font)

    def on_update(self, delta_time: float) -> None:
        if self._battle_done:
            return

        self._acc += delta_time
        if self._acc < self.tick_seconds:
            return
        self._acc = 0.0

        if self.engine.is_battle_over():
            self._battle_done = True
            return

        ready = self.engine.ready_combatants()
        for actor in ready:
            if not actor.alive:
                continue
            enemies = self.engine.alive_enemies(actor)
            if not enemies:
                break
            if actor.team == "player":
                action = self._player_action_mode.get(actor.name, "attack")
            else:
                action = self.engine.choose_npc_action(actor, enemies)
            self.engine.execute_action(actor, action)
            if self.engine.is_battle_over():
                self._battle_done = True
                break

        self.engine.advance_tick()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        del button, modifiers
        if self._battle_done:
            return

        if self._contains(self.attack_btn, x, y) and self._selected_player_name:
            self._player_action_mode[self._selected_player_name] = "attack"
            return
        if self._contains(self.move_btn, x, y) and self._selected_player_name:
            self._player_action_mode[self._selected_player_name] = "move"
            return

        tile_x = int((x - self.grid_origin_x) // self.tile_px)
        tile_y = int((y - self.grid_origin_y) // self.tile_px)
        if not (0 <= tile_x < self.engine.map_width and 0 <= tile_y < self.engine.map_height):
            return

        for actor in self.engine.actors:
            if actor.team == "player" and actor.alive and actor.x == tile_x and actor.y == tile_y:
                self._selected_player_name = actor.name
                return

    @staticmethod
    def _rect_points(rect: arcade.LRBT) -> tuple[float, float, float, float]:
        return rect.left, rect.right, rect.bottom, rect.top

    @staticmethod
    def _contains(rect: arcade.LRBT, x: float, y: float) -> bool:
        return rect.left <= x <= rect.right and rect.bottom <= y <= rect.top


def build_default_engine(*, seed: int = 42) -> CombatSceneEngine:
    action_defs = {
        "attack": ActionDefinition(key="attack", label="공격", tick_cost=9),
        "move": ActionDefinition(key="move", label="이동", tick_cost=5),
    }
    actors = [
        Combatant(name="에린", team="player", hp=42, attack=9, agility=7, x=2, y=1, icon="P"),
        Combatant(name="브람", team="player", hp=38, attack=11, agility=5, x=1, y=3, icon="Q"),
        Combatant(name="슬라임A", team="enemy", hp=30, attack=8, agility=4, x=10, y=5, icon="e"),
        Combatant(name="고블린B", team="enemy", hp=34, attack=10, agility=6, x=12, y=3, icon="g"),
    ]
    return CombatSceneEngine(actors=actors, action_defs=action_defs, rng=random.Random(seed))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Arcade ATB 전투 씬 단독 실행")
    parser.add_argument("--seed", type=int, default=42, help="난수 시드")
    parser.add_argument("--tick-seconds", type=float, default=1.0, help="틱 진행 간격(초)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = build_default_engine(seed=args.seed)

    if arcade is None:
        raise RuntimeError("실행하려면 `pip install arcade`가 필요합니다.")

    CombatSceneArcadeWindow(engine, tick_seconds=args.tick_seconds)
    arcade.run()


if __name__ == "__main__":
    main()
