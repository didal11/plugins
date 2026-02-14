#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""텍스트 기반 마을 시뮬레이션 실행기.

pygame 화면 없이 시뮬레이션 코어(VillageGame)의 시간 틱을 진행하고,
각 틱의 전체 상태를 콘솔 텍스트로 상세 출력한다.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from typing import Dict, Iterable, Tuple

from config import SCREEN_H, SCREEN_W
from village_sim import BASE_TILE_SIZE, VillageGame, world_px_to_tile


def _alive_count(game: VillageGame) -> int:
    return sum(1 for npc in game.npcs if npc.status.hp > 0)


def _avg(values: Iterable[int]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return float(sum(vals)) / float(len(vals))


def _fmt_inventory(inv: Dict[str, int]) -> str:
    if not inv:
        return "(없음)"
    return ", ".join(f"{k}:{v}" for k, v in sorted(inv.items()))


def _fmt_kv_dict(data: Dict[str, object]) -> str:
    if not data:
        return "(없음)"
    return ", ".join(f"{k}={data[k]}" for k in sorted(data.keys()))


def _camera_player_position(game: VillageGame) -> Tuple[float, float, int, int]:
    cam_x, cam_y = game.camera.x, game.camera.y
    center_world_x = cam_x + (SCREEN_W / game.camera.zoom) / 2.0
    center_world_y = cam_y + (SCREEN_H / game.camera.zoom) / 2.0
    center_tile_x, center_tile_y = world_px_to_tile(center_world_x, center_world_y)
    return center_world_x, center_world_y, center_tile_x, center_tile_y


def _print_tick_snapshot(game: VillageGame, tick: int) -> None:
    alive = _alive_count(game)
    avg_hunger = _avg(n.status.hunger for n in game.npcs if n.status.hp > 0)
    total_money = sum(max(0, int(n.status.money)) for n in game.npcs)
    recent_logs = game.logs[-3:]

    print(f"\n=== Tick {tick} | {game.time} ===")
    print("[요약]")
    print(f"- 생존 NPC: {alive}/{len(game.npcs)}")
    print(f"- 평균 배고픔: {avg_hunger:.1f}")
    print(f"- 총 소지금: {total_money}G")

    print("\n[시스템 설정]")
    print(f"BASE_TILE_SIZE={BASE_TILE_SIZE}, SCREEN={SCREEN_W}x{SCREEN_H}")
    print(f"sim_settings: {_fmt_kv_dict(game.sim_settings)}")
    print(f"combat_settings: {_fmt_kv_dict(game.combat_settings)}")

    cwx, cwy, ctx, cty = _camera_player_position(game)
    print("\n[플레이어(카메라) 좌표]")
    print(f"- 카메라 좌상단 월드좌표=({game.camera.x:.1f}, {game.camera.y:.1f}), zoom={game.camera.zoom:.2f}")
    print(f"- 카메라 중심 월드좌표=({cwx:.1f}, {cwy:.1f}), 타일좌표=({ctx}, {cty})")

    print("\n[엔티티(작업대/자원) 전체 상태]")
    if not game.entities:
        print("- (엔티티 없음)")
    for idx, ent in enumerate(game.entities, start=1):
        ent_type = str(ent.get("type", ""))
        name = str(ent.get("name", ""))
        ex = int(ent.get("x", 0))
        ey = int(ent.get("y", 0))
        stock = int(ent.get("stock", 0)) if ent_type == "resource" else "-"
        print(f"- 엔티티#{idx} type={ent_type} name={name} tile=({ex}, {ey}) stock={stock}")

    print("\n[엔티티(건물) 전체 상태]")
    for idx, building in enumerate(game.buildings, start=1):
        state = game.bstate[building.name]
        rect = building.rect_tiles
        occupants = [n.traits.name for n in game.npcs if n.location_building is not None and n.location_building.name == building.name and n.status.hp > 0]
        print(
            f"- 건물#{idx} name={building.name} zone={building.zone.value} "
            f"rect_tiles=(x:{rect.x}, y:{rect.y}, w:{rect.w}, h:{rect.h}) "
            f"task={state.task} progress={state.task_progress} last_event={state.last_event or '(없음)'}"
        )
        print(f"  재고: {_fmt_inventory(state.inventory)}")
        print(f"  현재 인원({len(occupants)}): {', '.join(occupants) if occupants else '(없음)'}")

    print("\n[NPC 전체 상태]")
    for idx, npc in enumerate(game.npcs, start=1):
        traits = asdict(npc.traits)
        status = asdict(npc.status)
        traits["job"] = npc.traits.job.value
        wx, wy = npc.x, npc.y
        tx, ty = world_px_to_tile(wx, wy)
        target_name = npc.target_building.name if npc.target_building is not None else "(없음)"
        location_name = npc.location_building.name if npc.location_building is not None else "(마을 밖/이동중)"
        path_preview = npc.path[:5]
        print(f"- NPC#{idx} {npc.traits.name}")
        print(f"  - 위치: world=({wx:.1f}, {wy:.1f}) tile=({tx}, {ty})")
        print(f"  - 이동: stage={npc.stage.value}, target_building={target_name}, target_outside_tile={npc.target_outside_tile}, path_len={len(npc.path)}, path_preview={path_preview}")
        print(f"  - 소속: home={npc.home_building.name}, location={location_name}")
        print(f"  - traits: {_fmt_kv_dict(traits)}")
        print(f"  - status: {_fmt_kv_dict(status)}")
        print(f"  - inventory: {_fmt_inventory(npc.inventory)}")

    if recent_logs:
        print("\n[최근 로그 3개]")
        for ln in recent_logs:
            print(f"- {ln}")
    else:
        print("\n[최근 로그 3개] (없음)")


def run_text_simulation(ticks: int, seed: int) -> None:
    game = VillageGame(seed=seed)

    print(f"[TEXT-SIM] 시작 seed={seed}, ticks={ticks}")
    for tick in range(1, ticks + 1):
        game.sim_tick_1hour()
        _print_tick_snapshot(game, tick)

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
