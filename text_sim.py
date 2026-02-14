#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""텍스트 기반 마을 시뮬레이션 실행기.

pygame 화면 없이 시뮬레이션 코어(VillageGame)의 시간 틱을 진행하고,
각 틱의 핵심 상태를 콘솔 텍스트로 출력한다.
"""

from __future__ import annotations

import argparse
from typing import Iterable

from village_sim import VillageGame


def _alive_count(game: VillageGame) -> int:
    return sum(1 for npc in game.npcs if npc.status.hp > 0)


def _avg(values: Iterable[int]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return float(sum(vals)) / float(len(vals))


def run_text_simulation(ticks: int, seed: int) -> None:
    game = VillageGame(seed=seed)

    print(f"[TEXT-SIM] 시작 seed={seed}, ticks={ticks}")
    for tick in range(1, ticks + 1):
        game.sim_tick_1hour()
        alive = _alive_count(game)
        avg_hunger = _avg(n.status.hunger for n in game.npcs if n.status.hp > 0)
        total_money = sum(max(0, int(n.status.money)) for n in game.npcs)
        recent_logs = game.logs[-3:]

        print(f"\n=== Tick {tick} | {game.time} ===")
        print(f"생존 NPC: {alive}/{len(game.npcs)} | 평균 배고픔: {avg_hunger:.1f} | 총 소지금: {total_money}G")
        if recent_logs:
            print("최근 로그:")
            for ln in recent_logs:
                print(f"- {ln}")
        else:
            print("최근 로그: (없음)")

    print("\n[TEXT-SIM] 완료")


def main() -> None:
    parser = argparse.ArgumentParser(description="텍스트 기반 마을 시뮬레이션")
    parser.add_argument("--ticks", type=int, default=10, help="진행할 시간 틱 수(기본: 10)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드(기본: 42)")
    args = parser.parse_args()

    if args.ticks <= 0:
        raise SystemExit("--ticks 는 1 이상이어야 합니다.")

    run_text_simulation(ticks=args.ticks, seed=args.seed)


if __name__ == "__main__":
    main()
