#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""ASCII 감성 전투 씬 프로토타입 (아케이드 전용 실행)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import random
from typing import Dict, List, Optional, Sequence

try:
    import arcade
except ImportError:  # optional dependency
    arcade = None


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
    position: int
    next_action_tick: int = 0
    alive: bool = True
    icon: str = "?"
    last_action: str = "대기"

    def schedule_next(self, tick_cost: int, now_tick: int) -> None:
        base = max(self.next_action_tick, now_tick)
        self.next_action_tick = base + max(1, tick_cost)


@dataclass
class CombatSceneEngine:
    actors: List[Combatant]
    action_defs: Dict[str, ActionDefinition]
    rng: random.Random = field(default_factory=random.Random)
    timeline_width: int = 32
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

    def choose_npc_action(self, actor: Combatant, enemies: Sequence[Combatant]) -> str:
        nearest = min(abs(x.position - actor.position) for x in enemies)
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

        target = min(enemies, key=lambda x: abs(x.position - actor.position))
        self._execute_attack(actor, target)
        actor.schedule_next(self.action_defs["attack"].tick_cost, self.current_tick)

    def advance_tick(self) -> None:
        self.current_tick += 1

    def timeline_str(self) -> str:
        start = self.current_tick
        end = start + self.timeline_width
        line = ["─"] * self.timeline_width
        token_buckets: Dict[int, List[str]] = {}

        for actor in self.actors:
            if not actor.alive:
                continue
            if start <= actor.next_action_tick < end:
                offset = actor.next_action_tick - start
                token_buckets.setdefault(offset, []).append(actor.icon)

        for idx, tokens in token_buckets.items():
            line[idx] = "".join(tokens)

        return f"[{start:03}-{end:03}] {''.join(line)}"

    def _execute_move(self, actor: Combatant, enemies: Sequence[Combatant]) -> None:
        target = min(enemies, key=lambda x: abs(x.position - actor.position))
        before = actor.position
        if actor.position < target.position:
            actor.position += 1
        elif actor.position > target.position:
            actor.position -= 1
        actor.last_action = self.action_defs["move"].label
        self.log.append(
            f"[T{self.current_tick:03}] {actor.name} 이동 {before}->{actor.position} (+{self.action_defs['move'].tick_cost}틱)"
        )

    def _execute_attack(self, actor: Combatant, target: Combatant) -> None:
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


def run_terminal(engine: CombatSceneEngine, *, player_auto: bool, max_ticks: int) -> None:
    print("=== ASCII COMBAT SCENE (terminal) ===")
    while not engine.is_battle_over() and engine.current_tick <= max_ticks:
        _render_terminal(engine)
        ready = engine.ready_combatants()
        if not ready:
            engine.advance_tick()
            continue

        for actor in ready:
            if not actor.alive:
                continue
            enemies = engine.alive_enemies(actor)
            if not enemies:
                break

            if actor.team == "player" and not player_auto:
                action = _prompt_player_action(engine, actor)
            elif actor.team == "player" and player_auto:
                action = engine.choose_npc_action(actor, enemies)
            else:
                action = engine.choose_npc_action(actor, enemies)

            engine.execute_action(actor, action)
            if engine.is_battle_over():
                break

        engine.advance_tick()

    _render_terminal(engine)
    winner = engine.winner_team()
    if winner:
        print(f"\n결과: {winner} 팀 승리")
    else:
        print("\n결과: 무승부")


def _prompt_player_action(engine: CombatSceneEngine, actor: Combatant) -> str:
    while True:
        print(
            f"\n[입력] {actor.name} 행동 선택: "
            f"1) {engine.action_defs['attack'].label}({engine.action_defs['attack'].tick_cost}틱) "
            f"2) {engine.action_defs['move'].label}({engine.action_defs['move'].tick_cost}틱)"
        )
        raw = input("> ").strip().lower()
        if raw in {"1", "a", "attack", "공격"}:
            return "attack"
        if raw in {"2", "m", "move", "이동"}:
            return "move"
        print("잘못된 입력입니다. 1(공격) 또는 2(이동)")


def _render_terminal(engine: CombatSceneEngine) -> None:
    print("\n" + "=" * 72)
    print(f"TICK {engine.current_tick:03}")
    print(engine.timeline_str())
    print("- 상태")
    for actor in sorted(engine.actors, key=lambda x: (x.team, x.name)):
        state = "DOWN" if not actor.alive else f"HP:{actor.hp:02} POS:{actor.position:02} NEXT:T{actor.next_action_tick:03}"
        print(f"  {actor.icon} {actor.name:<10} [{actor.team:^6}] {state} | last:{actor.last_action}")
    print("- 최근 로그")
    for row in engine.log[-5:]:
        print("  " + row)


class CombatSceneArcadeWindow(arcade.Window if arcade else object):
    def __init__(self, engine: CombatSceneEngine, tick_seconds: float = 0.35):
        if arcade is None:
            raise RuntimeError("arcade 패키지가 설치되어 있지 않습니다.")
        super().__init__(1100, 720, "Combat Scene (Arcade Click UI)")
        self.engine = engine
        self.tick_seconds = max(0.05, float(tick_seconds))
        self._acc = 0.0

        self._player_waiting: Optional[Combatant] = None
        self._queued_ready: List[Combatant] = []
        self._battle_done = False

        self.attack_btn = arcade.LRBT(80, 280, 120, 60)
        self.move_btn = arcade.LRBT(320, 520, 120, 60)

    def on_draw(self) -> None:
        self.clear((16, 18, 22))
        arcade.draw_text(f"TICK {self.engine.current_tick:03}", 30, 680, arcade.color.LIGHT_GRAY, 18)
        arcade.draw_text(self.engine.timeline_str(), 30, 650, arcade.color.BRIGHT_GREEN, 16, font_name="Courier New")

        y = 610
        arcade.draw_text("상태", 30, y, arcade.color.WHITE, 15)
        y -= 25
        for actor in sorted(self.engine.actors, key=lambda x: (x.team, x.name)):
            text = f"{actor.icon} {actor.name:<8} [{actor.team}] "
            text += "DOWN" if not actor.alive else f"HP:{actor.hp:02} POS:{actor.position:02} NEXT:{actor.next_action_tick:03}"
            color = arcade.color.LIGHT_GRAY if actor.alive else arcade.color.DARK_GRAY
            arcade.draw_text(text, 30, y, color, 13, font_name="Courier New")
            y -= 22

        arcade.draw_text("최근 로그", 30, 250, arcade.color.WHITE, 15)
        y = 225
        for row in self.engine.log[-8:]:
            arcade.draw_text(row, 30, y, arcade.color.ASH_GREY, 12, font_name="Courier New")
            y -= 18

        # 버튼
        attack_color = arcade.color.DARK_SPRING_GREEN if self._player_waiting else arcade.color.DARK_SLATE_GRAY
        move_color = arcade.color.INDIGO if self._player_waiting else arcade.color.DARK_SLATE_GRAY
        arcade.draw_lrbt_rectangle_filled(*self.attack_btn, attack_color)
        arcade.draw_lrbt_rectangle_filled(*self.move_btn, move_color)
        arcade.draw_text("공격", 150, 83, arcade.color.WHITE, 18, anchor_x="center")
        arcade.draw_text("이동", 390, 83, arcade.color.WHITE, 18, anchor_x="center")

        if self._battle_done:
            winner = self.engine.winner_team()
            msg = f"전투 종료 - 승리 팀: {winner}" if winner else "전투 종료 - 무승부"
            arcade.draw_text(msg, 650, 80, arcade.color.YELLOW, 20)
        elif self._player_waiting:
            arcade.draw_text(f"{self._player_waiting.name} 행동을 클릭으로 선택하세요", 560, 80, arcade.color.YELLOW, 18)
        else:
            arcade.draw_text("진행 중...", 560, 80, arcade.color.LIGHT_GRAY, 16)

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

        if self._player_waiting:
            return

        if not self._queued_ready:
            self._queued_ready = self.engine.ready_combatants()
            if not self._queued_ready:
                self.engine.advance_tick()
                return

        while self._queued_ready:
            actor = self._queued_ready.pop(0)
            if not actor.alive:
                continue
            enemies = self.engine.alive_enemies(actor)
            if not enemies:
                break
            if actor.team == "player":
                self._player_waiting = actor
                return
            action = self.engine.choose_npc_action(actor, enemies)
            self.engine.execute_action(actor, action)
            if self.engine.is_battle_over():
                self._battle_done = True
                return

        if not self._player_waiting:
            self.engine.advance_tick()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        del button, modifiers
        if not self._player_waiting or self._battle_done:
            return

        actor = self._player_waiting
        if self._contains(self.attack_btn, x, y):
            self.engine.execute_action(actor, "attack")
            self._player_waiting = None
        elif self._contains(self.move_btn, x, y):
            self.engine.execute_action(actor, "move")
            self._player_waiting = None
        else:
            return

        if self.engine.is_battle_over():
            self._battle_done = True
            return

        # 플레이어 행동 후 같은 틱 대기열 이어서 처리
        while self._queued_ready:
            npc = self._queued_ready.pop(0)
            if not npc.alive:
                continue
            enemies = self.engine.alive_enemies(npc)
            if not enemies:
                break
            if npc.team == "player":
                self._player_waiting = npc
                return
            action = self.engine.choose_npc_action(npc, enemies)
            self.engine.execute_action(npc, action)
            if self.engine.is_battle_over():
                self._battle_done = True
                return

        if not self._player_waiting:
            self.engine.advance_tick()

    @staticmethod
    def _contains(rect: arcade.LRBT, x: float, y: float) -> bool:
        return rect.left <= x <= rect.right and rect.bottom <= y <= rect.top


def build_default_engine(*, seed: int = 42) -> CombatSceneEngine:
    action_defs = {
        "attack": ActionDefinition(key="attack", label="공격", tick_cost=9),
        "move": ActionDefinition(key="move", label="이동", tick_cost=5),
    }
    actors = [
        Combatant(name="에린", team="player", hp=42, attack=9, agility=7, position=2, icon="P"),
        Combatant(name="브람", team="player", hp=38, attack=11, agility=5, position=0, icon="Q"),
        Combatant(name="슬라임A", team="enemy", hp=30, attack=8, agility=4, position=11, icon="e"),
        Combatant(name="고블린B", team="enemy", hp=34, attack=10, agility=6, position=13, icon="g"),
    ]
    return CombatSceneEngine(actors=actors, action_defs=action_defs, rng=random.Random(seed))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Arcade ATB 전투 씬 단독 실행")
    parser.add_argument("--seed", type=int, default=42, help="난수 시드")
    parser.add_argument("--tick-seconds", type=float, default=0.35, help="틱 진행 간격(초)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = build_default_engine(seed=args.seed)

    if arcade is None:
        raise RuntimeError("실행하려면 `pip install arcade`가 필요합니다.")

    window = CombatSceneArcadeWindow(engine, tick_seconds=args.tick_seconds)
    arcade.run()


if __name__ == "__main__":
    main()
