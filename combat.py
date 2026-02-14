#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Combat subsystem.

전투 판정을 외부 모듈로 분리해 village_sim.py 에서 호출만 하도록 유지한다.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

from config import BASE_TILE_SIZE
from model import JobType, NPC

DEFAULT_COMBAT_CFG: Dict[str, object] = {
    "hostile_race": "적대",
    "engage_range_tiles": 2,
    "base_hit_chance": 0.75,
    "agility_evasion_scale": 0.015,
    "min_damage": 5,
    "max_damage": 14,
    "strength_damage_scale": 0.45,
    "adventurer_attack_bonus": 0.10,
    "hostile_attack_bonus": 0.05,
}


def _is_alive(npc: NPC) -> bool:
    return npc.status.hp > 0


def _distance_tiles(a: NPC, b: NPC) -> int:
    return abs(int(a.x // BASE_TILE_SIZE) - int(b.x // BASE_TILE_SIZE)) + abs(int(a.y // BASE_TILE_SIZE) - int(b.y // BASE_TILE_SIZE))


def _combat_cfg(cfg: Dict[str, object] | None) -> Dict[str, object]:
    src = cfg if isinstance(cfg, dict) else {}
    out = dict(DEFAULT_COMBAT_CFG)
    out.update(src)

    out["hostile_race"] = str(out.get("hostile_race", "적대")).strip() or "적대"
    out["engage_range_tiles"] = max(1, int(out.get("engage_range_tiles", 2)))
    out["base_hit_chance"] = max(0.05, min(0.99, float(out.get("base_hit_chance", 0.75))))
    out["agility_evasion_scale"] = max(0.0, float(out.get("agility_evasion_scale", 0.015)))
    out["min_damage"] = max(1, int(out.get("min_damage", 5)))
    out["max_damage"] = max(int(out["min_damage"]), int(out.get("max_damage", 14)))
    out["strength_damage_scale"] = max(0.0, float(out.get("strength_damage_scale", 0.45)))
    out["adventurer_attack_bonus"] = float(out.get("adventurer_attack_bonus", 0.10))
    out["hostile_attack_bonus"] = float(out.get("hostile_attack_bonus", 0.05))
    return out


def _attack_once(attacker: NPC, defender: NPC, cfg: Dict[str, object], rng: random.Random) -> str:
    hit = float(cfg["base_hit_chance"])
    hit += float(cfg["adventurer_attack_bonus"]) if attacker.traits.job == JobType.ADVENTURER else 0.0
    if attacker.traits.race == str(cfg["hostile_race"]):
        hit += float(cfg["hostile_attack_bonus"])
    hit -= max(0.0, defender.status.agility - attacker.status.agility) * float(cfg["agility_evasion_scale"])

    if rng.random() > max(0.05, min(0.99, hit)):
        return f"{attacker.traits.name} -> {defender.traits.name} 공격 빗나감"

    base = rng.randint(int(cfg["min_damage"]), int(cfg["max_damage"]))
    dmg = max(1, int(base + attacker.status.strength * float(cfg["strength_damage_scale"])))
    before = defender.status.hp
    defender.status.hp = max(0, defender.status.hp - dmg)
    if defender.status.hp <= 0:
        defender.path = []
        defender.target_building = None
        defender.target_outside_tile = None
        return f"{attacker.traits.name} -> {defender.traits.name} {before}->{defender.status.hp} (쓰러짐)"
    return f"{attacker.traits.name} -> {defender.traits.name} {before}->{defender.status.hp}"


def resolve_combat_round(npcs: List[NPC], cfg: Dict[str, object] | None, rng: random.Random) -> List[str]:
    settings = _combat_cfg(cfg)
    events: List[str] = []
    hostile_race = str(settings["hostile_race"])
    engage = int(settings["engage_range_tiles"])

    hostiles = [n for n in npcs if _is_alive(n) and n.traits.race == hostile_race]
    adventurers = [n for n in npcs if _is_alive(n) and n.traits.job == JobType.ADVENTURER and n.traits.race != hostile_race]

    used_pairs: set[Tuple[int, int]] = set()

    for adv in adventurers:
        nearby = [h for h in hostiles if _distance_tiles(adv, h) <= engage]
        if not nearby:
            continue
        target = min(nearby, key=lambda h: _distance_tiles(adv, h))
        pair = (id(adv), id(target))
        if pair in used_pairs:
            continue
        used_pairs.add(pair)

        events.append(_attack_once(adv, target, settings, rng))
        if _is_alive(target):
            events.append(_attack_once(target, adv, settings, rng))

    return events
