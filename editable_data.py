#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Editable JSON data store for items, NPC templates, and combat tuning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).parent / "data"
ITEMS_FILE = DATA_DIR / "items.json"
NPCS_FILE = DATA_DIR / "npcs.json"
COMBAT_FILE = DATA_DIR / "combat.json"

DEFAULT_ITEMS: List[Dict[str, str]] = [
    {"key": "bread", "display": "빵"},
    {"key": "meat", "display": "고기"},
    {"key": "fish", "display": "생선"},
    {"key": "potion", "display": "포션"},
    {"key": "wood", "display": "목재"},
    {"key": "ore", "display": "광석"},
]

DEFAULT_NPCS: List[Dict[str, object]] = [
    {"name": "엘린", "race": "인간", "gender": "여", "age": 24, "height_cm": 167, "weight_kg": 56, "job": "모험가", "goal": "적대 사냥", "max_hp": 120, "hp": 120, "strength": 16, "agility": 13},
    {"name": "보른", "race": "드워프", "gender": "남", "age": 39, "height_cm": 146, "weight_kg": 76, "job": "대장장이", "goal": "명품 제작", "max_hp": 110, "hp": 110, "strength": 13, "agility": 8},
    {"name": "마라", "race": "엘프", "gender": "여", "age": 31, "height_cm": 178, "weight_kg": 60, "job": "약사", "goal": "치유 연구", "max_hp": 95, "hp": 95, "strength": 8, "agility": 12},
    {"name": "레오", "race": "인간", "gender": "남", "age": 28, "height_cm": 175, "weight_kg": 69, "job": "농부", "goal": "풍작", "max_hp": 105, "hp": 105, "strength": 10, "agility": 9},
    {"name": "시안", "race": "엘프", "gender": "기타", "age": 26, "height_cm": 182, "weight_kg": 64, "job": "어부", "goal": "대어 잡기", "max_hp": 100, "hp": 100, "strength": 9, "agility": 11},
    {"name": "그림자", "race": "적대", "gender": "기타", "age": 22, "height_cm": 180, "weight_kg": 70, "job": "모험가", "goal": "배회", "max_hp": 90, "hp": 90, "strength": 12, "agility": 10},
]

DEFAULT_COMBAT: Dict[str, object] = {
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

VALID_JOBS = ["모험가", "농부", "어부", "대장장이", "약사"]


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ITEMS_FILE.exists():
        _write_json(ITEMS_FILE, DEFAULT_ITEMS)
    if not NPCS_FILE.exists():
        _write_json(NPCS_FILE, DEFAULT_NPCS)
    if not COMBAT_FILE.exists():
        _write_json(COMBAT_FILE, DEFAULT_COMBAT)


def load_item_defs() -> List[Dict[str, str]]:
    ensure_data_files()
    try:
        raw = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return list(DEFAULT_ITEMS)
    out: List[Dict[str, str]] = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        key = str(it.get("key", "")).strip()
        display = str(it.get("display", "")).strip()
        if key and display:
            out.append({"key": key, "display": display})
    return out or list(DEFAULT_ITEMS)


def save_item_defs(items: List[Dict[str, str]]) -> None:
    ensure_data_files()
    clean: List[Dict[str, str]] = []
    for it in items:
        key = str(it.get("key", "")).strip()
        display = str(it.get("display", "")).strip()
        if key and display:
            clean.append({"key": key, "display": display})
    _write_json(ITEMS_FILE, clean)


def _clean_npc(it: Dict[str, object]) -> Dict[str, object] | None:
    name = str(it.get("name", "")).strip()
    if not name:
        return None
    race = str(it.get("race", "인간")).strip() or "인간"
    gender = str(it.get("gender", "기타")).strip() or "기타"
    goal = str(it.get("goal", "돈벌기")).strip() or "돈벌기"
    job = str(it.get("job", "농부")).strip() or "농부"
    if job not in VALID_JOBS:
        job = "농부"
    try:
        age = int(it.get("age", 25))
        height_cm = int(it.get("height_cm", 170))
        weight_kg = int(it.get("weight_kg", 65))
        max_hp = max(1, int(it.get("max_hp", 100)))
        hp = max(0, min(max_hp, int(it.get("hp", max_hp))))
        strength = max(1, int(it.get("strength", 10)))
        agility = max(1, int(it.get("agility", 10)))
    except Exception:
        return None
    return {
        "name": name,
        "race": race,
        "gender": gender,
        "age": age,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "job": job,
        "goal": goal,
        "max_hp": max_hp,
        "hp": hp,
        "strength": strength,
        "agility": agility,
    }


def load_npc_templates() -> List[Dict[str, object]]:
    ensure_data_files()
    try:
        raw = json.loads(NPCS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return list(DEFAULT_NPCS)
    out: List[Dict[str, object]] = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        clean = _clean_npc(it)
        if clean is not None:
            out.append(clean)
    return out or list(DEFAULT_NPCS)


def save_npc_templates(npcs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    clean: List[Dict[str, object]] = []
    for it in npcs:
        if isinstance(it, dict):
            npc = _clean_npc(it)
            if npc is not None:
                clean.append(npc)
    _write_json(NPCS_FILE, clean)


def load_combat_settings() -> Dict[str, object]:
    ensure_data_files()
    try:
        raw = json.loads(COMBAT_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return dict(DEFAULT_COMBAT)
    except Exception:
        return dict(DEFAULT_COMBAT)
    out = dict(DEFAULT_COMBAT)
    out.update(raw)
    out["hostile_race"] = str(out.get("hostile_race", "적대")).strip() or "적대"
    out["engage_range_tiles"] = max(1, int(out.get("engage_range_tiles", 2)))
    out["base_hit_chance"] = max(0.05, min(0.99, float(out.get("base_hit_chance", 0.75))))
    out["agility_evasion_scale"] = max(0.0, float(out.get("agility_evasion_scale", 0.015)))
    out["min_damage"] = max(1, int(out.get("min_damage", 5)))
    out["max_damage"] = max(out["min_damage"], int(out.get("max_damage", 14)))
    out["strength_damage_scale"] = max(0.0, float(out.get("strength_damage_scale", 0.45)))
    out["adventurer_attack_bonus"] = float(out.get("adventurer_attack_bonus", 0.10))
    out["hostile_attack_bonus"] = float(out.get("hostile_attack_bonus", 0.05))
    return out


def save_combat_settings(settings: Dict[str, object]) -> None:
    ensure_data_files()
    merged = dict(load_combat_settings())
    merged.update(settings)
    _write_json(COMBAT_FILE, merged)
