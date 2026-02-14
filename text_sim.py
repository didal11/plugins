#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""텍스트 기반 마을 시뮬레이션 실행기.

요청 기준으로 매 틱마다 아래를 전부 출력한다.
- 시스템 설정값(sim_settings/combat_settings)
- 플레이어 관점 좌표(카메라 좌표/줌)
- 엔티티 목록(타입/이름/좌표/재고)
- 건물 상태(작업/진척/이벤트/재고)
- 모든 NPC의 모든 특성/스테이터스/좌표/경로/인벤토리
"""

from __future__ import annotations

import argparse
from typing import Dict, Iterable, List, Optional

from editable_data import load_entities
from village_sim import VillageGame


def _alive_count(game: VillageGame) -> int:
    return sum(1 for npc in game.npcs if npc.status.hp > 0)


def _avg(values: Iterable[int]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return float(sum(vals)) / float(len(vals))


def _fmt_inventory(inv: Dict[str, int]) -> str:
    if not inv:
        return "{}"
    parts = [f"{k}:{int(v)}" for k, v in sorted(inv.items(), key=lambda x: x[0])]
    return "{" + ", ".join(parts) + "}"


def _dump_system(game: VillageGame) -> None:
    print("[SYSTEM]")
    print(f"- 시간: {game.time}")
    print(
        "- 카메라(플레이어 관점) 좌표: "
        f"x={game.camera.x:.1f}, y={game.camera.y:.1f}, zoom={game.camera.zoom:.3f}"
    )
    print(f"- 선택 상태: type={game.selection_type.value}, npc={game.selected_npc}, building={game.selected_building}")
    print(f"- 모달: open={game.modal_open}, kind={game.modal_kind.value}")
    print(f"- 시뮬 설정값: {game.sim_settings}")
    print(f"- 전투 설정값: {game.combat_settings}")
    if game.last_economy_snapshot is not None:
        snap = game.last_economy_snapshot
        print(
            "- 경제 스냅샷: "
            f"total_money={snap.total_money}, market_food_stock={snap.market_food_stock}, crafted_stock={snap.crafted_stock}"
        )


def _dump_entities() -> None:
    entities = load_entities()
    print(f"[ENTITIES] count={len(entities)}")
    for idx, e in enumerate(entities):
        etype = str(e.get("type", ""))
        name = str(e.get("name", ""))
        x = int(e.get("x", 0))
        y = int(e.get("y", 0))
        stock: Optional[int] = None
        if "stock" in e:
            stock = int(e.get("stock", 0))
        if stock is None:
            print(f"- #{idx:02d} {etype}:{name} pos=({x},{y})")
        else:
            print(f"- #{idx:02d} {etype}:{name} pos=({x},{y}) stock={stock}")


def _dump_buildings(game: VillageGame) -> None:
    print(f"[BUILDINGS] count={len(game.buildings)}")
    for b in game.buildings:
        st = game.bstate.get(b.name)
        if st is None:
            print(f"- {b.name} zone={b.zone.value} state=(none)")
            continue
        print(
            f"- {b.name} zone={b.zone.value} rect=({b.rect_tiles.x},{b.rect_tiles.y},{b.rect_tiles.w},{b.rect_tiles.h}) "
            f"task={st.task} progress={st.task_progress} last_event={st.last_event!r} inv={_fmt_inventory(st.inventory)}"
        )


def _dump_npcs(game: VillageGame) -> None:
    print(f"[NPCS] count={len(game.npcs)}")
    for i, npc in enumerate(game.npcs):
        tr = npc.traits
        st = npc.status
        home = npc.home_building.name if npc.home_building is not None else None
        target = npc.target_building.name if npc.target_building is not None else None
        loc = npc.location_building.name if npc.location_building is not None else None
        print(
            f"- #{i:02d} name={tr.name} race={tr.race} gender={tr.gender} age={tr.age} job={tr.job.value} "
            f"hostile={tr.is_hostile}"
        )
        print(
            "  traits_bonus="
            f"(str={tr.race_str_bonus},agi={tr.race_agi_bonus},hp={tr.race_hp_bonus},speed={tr.race_speed_bonus})"
        )
        print(
            "  status="
            f"(hp={st.hp}/{st.max_hp},str={st.strength},agi={st.agility},money={st.money},"
            f"happiness={st.happiness},hunger={st.hunger},fatigue={st.fatigue})"
        )
        print(
            "  position="
            f"(x={npc.x:.1f},y={npc.y:.1f}) stage={npc.stage.value} path_len={len(npc.path)} "
            f"home={home} target={target} location={loc} target_outside_tile={npc.target_outside_tile}"
        )
        print(f"  path={npc.path}")
        print(f"  inventory={_fmt_inventory(npc.inventory)}")


def run_text_simulation(ticks: int, seed: int) -> None:
    game = VillageGame(seed=seed)

    print(f"[TEXT-SIM] 시작 seed={seed}, ticks={ticks}")
    for tick in range(1, ticks + 1):
        game.sim_tick_1hour()
        alive = _alive_count(game)
        avg_hunger = _avg(n.status.hunger for n in game.npcs if n.status.hp > 0)
        total_money = sum(max(0, int(n.status.money)) for n in game.npcs)

        print(f"\n{'=' * 28} Tick {tick:02d} {'=' * 28}")
        print(f"[SUMMARY] 생존={alive}/{len(game.npcs)} 평균배고픔={avg_hunger:.2f} 총소지금={total_money}G")
        _dump_system(game)
        _dump_entities()
        _dump_buildings(game)
        _dump_npcs(game)

        print("[RECENT LOGS]")
        if game.logs:
            for ln in game.logs[-10:]:
                print(f"- {ln}")
        else:
            print("- (없음)")

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
