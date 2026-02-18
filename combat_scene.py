#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""ASCII 감성의 ATB/CTB 스타일 전투 씬 프로토타입.

요구사항 요약
- 상단에 항상 흐르는 틱 타임라인 표시
- 행동 선택 시 cost 만큼 다음 행동 시점(next_action_tick) 지연
- 예약 시점이 같은 구간에 여러 캐릭터가 겹칠 수 있음(오버랩 허용)
- 현재는 공격/이동만 구현하고, 행동 사전(action_defs)을 데이터 중심 확장 가능하게 구성
"""

from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import random
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class ActionDefinition:
    """행동 정의(향후 JSON/DB에서 로드 가능)."""

    key: str
    label: str
    tick_cost: int


@dataclass
class Combatant:
    """전투 참여자 상태."""

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
class CombatScene:
    actors: List[Combatant]
    action_defs: Dict[str, ActionDefinition]
    rng: random.Random = field(default_factory=random.Random)
    timeline_width: int = 32
    current_tick: int = 0
    log: List[str] = field(default_factory=list)

    def run(self, *, player_auto: bool = False, max_ticks: int = 300) -> None:
        print("=== ASCII COMBAT SCENE PROTOTYPE ===")
        while not self._is_battle_over() and self.current_tick <= max_ticks:
            self._render()
            ready = self._ready_combatants()
            if not ready:
                self.current_tick += 1
                continue

            for actor in ready:
                if not actor.alive:
                    continue
                self._take_turn(actor, player_auto=player_auto)
                if self._is_battle_over():
                    break

            self.current_tick += 1

        self._render()
        self._print_result()

    def _take_turn(self, actor: Combatant, *, player_auto: bool) -> None:
        enemies = [x for x in self.actors if x.alive and x.team != actor.team]
        if not enemies:
            return

        if actor.team == "player":
            action_key = self._choose_player_action(actor, player_auto=player_auto)
        else:
            action_key = self._choose_npc_action(actor, enemies)

        if action_key == "move":
            self._execute_move(actor, enemies)
            actor.schedule_next(self.action_defs["move"].tick_cost, self.current_tick)
            return

        # 기본: attack
        target = min(enemies, key=lambda x: abs(x.position - actor.position))
        self._execute_attack(actor, target)
        actor.schedule_next(self.action_defs["attack"].tick_cost, self.current_tick)

    def _choose_player_action(self, actor: Combatant, *, player_auto: bool) -> str:
        if player_auto:
            return self._choose_npc_action(actor, [x for x in self.actors if x.alive and x.team != actor.team])

        while True:
            print(
                f"\n[입력] {actor.name} 행동 선택: "
                f"1) {self.action_defs['attack'].label}({self.action_defs['attack'].tick_cost}틱) "
                f"2) {self.action_defs['move'].label}({self.action_defs['move'].tick_cost}틱)"
            )
            raw = input("> ").strip().lower()
            if raw in {"1", "a", "attack", "공격"}:
                return "attack"
            if raw in {"2", "m", "move", "이동"}:
                return "move"
            print("잘못된 입력입니다. 1(공격) 또는 2(이동)을 입력해주세요.")

    def _choose_npc_action(self, actor: Combatant, enemies: Sequence[Combatant]) -> str:
        nearest = min(abs(x.position - actor.position) for x in enemies)
        if nearest <= 1:
            return "attack"
        # 민첩이 높은 NPC는 좀 더 공격적으로 접근
        if actor.agility >= 7:
            return "move"
        return "attack" if self.rng.random() < 0.35 else "move"

    def _execute_move(self, actor: Combatant, enemies: Sequence[Combatant]) -> None:
        target = min(enemies, key=lambda x: abs(x.position - actor.position))
        before = actor.position
        if actor.position < target.position:
            actor.position += 1
        elif actor.position > target.position:
            actor.position -= 1
        actor.last_action = self.action_defs["move"].label
        self.log.append(
            f"[T{self.current_tick:03}] {actor.name} 이동 {before}->{actor.position} (다음 행동 T{actor.next_action_tick}+{self.action_defs['move'].tick_cost})"
        )

    def _execute_attack(self, actor: Combatant, target: Combatant) -> None:
        # 기본 적중/회피 계산(간단 버전)
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

    def _ready_combatants(self) -> List[Combatant]:
        ready = [x for x in self.actors if x.alive and x.next_action_tick <= self.current_tick]
        # 같은 틱에 겹친 예약(오버랩)을 그대로 허용하며, 처리 순서만 고정
        ready.sort(key=lambda x: (-x.agility, x.name))
        return ready

    def _is_battle_over(self) -> bool:
        alive_teams = {x.team for x in self.actors if x.alive}
        return len(alive_teams) <= 1

    def _timeline_str(self) -> str:
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
            line[idx] = "".join(tokens)  # 겹침을 한 칸에 문자열로 표시

        cursor = " " * min(self.timeline_width - 1, 0) + "^now"
        return f"[{start:03}-{end:03}] {''.join(line)}\n          {cursor}"

    def _render(self) -> None:
        print("\n" + "=" * 72)
        print(f"TICK {self.current_tick:03}")
        print(self._timeline_str())
        print("- 상태")
        for actor in sorted(self.actors, key=lambda x: (x.team, x.name)):
            state = "DOWN" if not actor.alive else f"HP:{actor.hp:02} POS:{actor.position:02} NEXT:T{actor.next_action_tick:03}"
            print(f"  {actor.icon} {actor.name:<10} [{actor.team:^6}] {state} | last:{actor.last_action}")

        print("- 최근 로그")
        for row in self.log[-5:]:
            print("  " + row)

    def _print_result(self) -> None:
        alive_teams = {x.team for x in self.actors if x.alive}
        if not alive_teams:
            print("\n결과: 무승부(전원 전투불능)")
            return
        winner = next(iter(alive_teams))
        print(f"\n결과: {winner} 팀 승리")


def build_default_scene(*, seed: int = 42) -> CombatScene:
    """독립 실행 가능한 기본 전투 씬 생성."""

    action_defs = {
        # 향후 data/actions 같은 외부 데이터로 치환 가능
        "attack": ActionDefinition(key="attack", label="공격", tick_cost=9),
        "move": ActionDefinition(key="move", label="이동", tick_cost=5),
    }

    actors = [
        Combatant(name="에린", team="player", hp=42, attack=9, agility=7, position=2, icon="P"),
        Combatant(name="브람", team="player", hp=38, attack=11, agility=5, position=0, icon="Q"),
        Combatant(name="슬라임A", team="enemy", hp=30, attack=8, agility=4, position=11, icon="e"),
        Combatant(name="고블린B", team="enemy", hp=34, attack=10, agility=6, position=13, icon="g"),
    ]

    return CombatScene(actors=actors, action_defs=action_defs, rng=random.Random(seed))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASCII ATB/CTB 전투 씬 단독 실행")
    parser.add_argument("--seed", type=int, default=42, help="난수 시드")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="플레이어 입력 없이 자동 전투로 실행(테스트/빠른 확인용)",
    )
    parser.add_argument("--max-ticks", type=int, default=200, help="최대 틱 수")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scene = build_default_scene(seed=args.seed)
    scene.run(player_auto=args.auto, max_ticks=args.max_ticks)


if __name__ == "__main__":
    main()
