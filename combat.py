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


def _is_alive(npc: NPC) -> bool:
    return npc.status.hp > 0


def _distance_tiles(a: NPC, b: NPC) -> int:
    return abs(int(a.x // BASE_TILE_SIZE) - int(b.x // BASE_TILE_SIZE)) + abs(int(a.y // BASE_TILE_SIZE) - int(b.y // BASE_TILE_SIZE))


def _attack_once(attacker: NPC, defender: NPC, cfg: Dict[str, object], rng: random.Random) -> str:
    hit = float(cfg.get("base_hit_chance",0.75))
    hit += float(cfg.get("adventurer_attack_bonus",0.0)) if attacker.traits.job == JobType.ADVENTURER else 0.0
    if getattr(attacker.traits, "is_hostile", False):
        hit += float(cfg.get("hostile_attack_bonus",0.0))
    hit -= max(0.0, defender.status.agility - attacker.status.agility) * float(cfg.get("agility_evasion_scale",0.015))

    if rng.random() > max(0.05, min(0.99, hit)):
        return f"{attacker.traits.name} -> {defender.traits.name} 공격 빗나감"

    base = rng.randint(int(cfg.get("min_damage",5)), int(cfg.get("max_damage",14)))
    dmg = max(1, int(base + attacker.status.strength * float(cfg.get("strength_damage_scale",0.45))))
    before = defender.status.hp
    defender.status.hp = max(0, defender.status.hp - dmg)
    if defender.status.hp <= 0:
        defender.path = []
        defender.target_outside_tile = None
        return f"{attacker.traits.name} -> {defender.traits.name} {before}->{defender.status.hp} (쓰러짐)"
    return f"{attacker.traits.name} -> {defender.traits.name} {before}->{defender.status.hp}"


def resolve_combat_round(npcs: List[NPC], cfg: Dict[str, object], rng: random.Random) -> List[str]:
    events: List[str] = []
    engage = int(cfg.get("engage_range_tiles", 2))

    hostiles = [n for n in npcs if _is_alive(n) and getattr(n.traits, "is_hostile", False)]
    adventurers = [n for n in npcs if _is_alive(n) and n.traits.job == JobType.ADVENTURER and not getattr(n.traits, "is_hostile", False)]

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

        events.append(_attack_once(adv, target, cfg, rng))
        if _is_alive(target):
            events.append(_attack_once(target, adv, cfg, rng))

    return events
