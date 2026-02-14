#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).parent / "data"
ITEMS_FILE = DATA_DIR / "items.json"
NPCS_FILE = DATA_DIR / "npcs.json"
MONSTERS_FILE = DATA_DIR / "monsters.json"
RACES_FILE = DATA_DIR / "races.json"
ENTITIES_FILE = DATA_DIR / "entities.json"
JOBS_FILE = DATA_DIR / "jobs.json"
SIM_SETTINGS_FILE = DATA_DIR / "sim_settings.json"

VALID_JOBS = ["모험가", "농부", "어부", "대장장이", "약사"]
VALID_GENDERS = ["남", "여", "기타"]

DEFAULT_RACES: List[Dict[str, object]] = [
    {"name": "인간", "is_hostile": False, "str_bonus": 0, "agi_bonus": 0, "hp_bonus": 0, "speed_bonus": 0.0},
    {"name": "엘프", "is_hostile": False, "str_bonus": -1, "agi_bonus": 2, "hp_bonus": -5, "speed_bonus": 12.0},
    {"name": "드워프", "is_hostile": False, "str_bonus": 2, "agi_bonus": -1, "hp_bonus": 10, "speed_bonus": -10.0},
    {"name": "거인", "is_hostile": True, "str_bonus": 4, "agi_bonus": -2, "hp_bonus": 35, "speed_bonus": -25.0},
    {"name": "고블린", "is_hostile": True, "str_bonus": -1, "agi_bonus": 3, "hp_bonus": -8, "speed_bonus": 18.0},
    {"name": "코볼트", "is_hostile": True, "str_bonus": 0, "agi_bonus": 2, "hp_bonus": -2, "speed_bonus": 10.0},
    {"name": "슬라임", "is_hostile": True, "str_bonus": 1, "agi_bonus": -2, "hp_bonus": 20, "speed_bonus": -20.0},
]

DEFAULT_ITEMS: List[Dict[str, object]] = [
    {"key": "wheat", "display": "밀", "is_craftable": False, "is_gatherable": True, "gather_time": 1, "gather_amount": 3, "gather_fatigue": 4, "gather_spot": "농장", "craft_inputs": {}, "craft_time": 0, "craft_fatigue": 0, "craft_station": "", "craft_amount": 0},
    {"key": "bread", "display": "빵", "is_craftable": True, "is_gatherable": False, "gather_time": 0, "gather_amount": 0, "gather_fatigue": 0, "gather_spot": "", "craft_inputs": {"wheat": 2}, "craft_time": 1, "craft_fatigue": 3, "craft_station": "화덕", "craft_amount": 1},
    {"key": "fish", "display": "생선", "is_craftable": False, "is_gatherable": True, "gather_time": 1, "gather_amount": 2, "gather_fatigue": 4, "gather_spot": "낚시터", "craft_inputs": {}, "craft_time": 0, "craft_fatigue": 0, "craft_station": "", "craft_amount": 0},
    {"key": "potion", "display": "포션", "is_craftable": True, "is_gatherable": False, "gather_time": 0, "gather_amount": 0, "gather_fatigue": 0, "gather_spot": "", "craft_inputs": {"herb": 2}, "craft_time": 2, "craft_fatigue": 5, "craft_station": "약제작대", "craft_amount": 1},
]

DEFAULT_ENTITIES: List[Dict[str, object]] = [
    {"type": "workbench", "name": "화덕", "x": 120, "y": 100},
    {"type": "workbench", "name": "약제작대", "x": 160, "y": 110},
    {"type": "resource", "name": "야생 약초 군락", "x": 280, "y": 210, "stock": 40},
    {"type": "resource", "name": "노천 광맥", "x": 300, "y": 220, "stock": 35},
]

DEFAULT_NPCS: List[Dict[str, object]] = [
    {"name": "엘린", "race": "인간", "gender": "여", "age": 24, "job": "모험가"},
    {"name": "보른", "race": "드워프", "gender": "남", "age": 39, "job": "대장장이"},
    {"name": "마라", "race": "엘프", "gender": "여", "age": 31, "job": "약사"},
    {"name": "레오", "race": "인간", "gender": "남", "age": 28, "job": "농부"},
    {"name": "시안", "race": "엘프", "gender": "기타", "age": 26, "job": "어부"},
]

DEFAULT_MONSTERS: List[Dict[str, object]] = [
    {"name": "들개 고블린", "race": "고블린", "gender": "기타", "age": 8, "job": "모험가"},
    {"name": "늪지 슬라임", "race": "슬라임", "gender": "기타", "age": 3, "job": "모험가"},
    {"name": "산악 코볼트", "race": "코볼트", "gender": "기타", "age": 9, "job": "모험가"},
]

DEFAULT_JOB_DEFS: List[Dict[str, object]] = [
    {"job": "모험가", "primary_output": {"ore": 1, "wood": 1}, "input_need": {}, "craft_output": {}, "sell_items": ["ore", "wood"], "sell_limit": 3},
    {"job": "농부", "primary_output": {"wheat": 3}, "input_need": {"wheat": 2}, "craft_output": {"bread": 1}, "sell_items": ["wheat", "bread"], "sell_limit": 4},
    {"job": "어부", "primary_output": {"fish": 2}, "input_need": {}, "craft_output": {}, "sell_items": ["fish"], "sell_limit": 3},
    {"job": "대장장이", "primary_output": {"ore": 1}, "input_need": {"ore": 2}, "craft_output": {"ingot": 1}, "sell_items": ["ingot", "ore"], "sell_limit": 2},
    {"job": "약사", "primary_output": {"herb": 2}, "input_need": {"herb": 2}, "craft_output": {"potion": 1}, "sell_items": ["potion", "herb"], "sell_limit": 2},
]

DEFAULT_SIM_SETTINGS: Dict[str, float] = {
    "npc_speed": 220.0,
    "hunger_gain_per_hour": 5.0,
    "fatigue_gain_per_hour": 4.0,
    "meal_hunger_restore": 30.0,
    "rest_fatigue_restore": 35.0,
    "potion_heal": 14.0,
}


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    defaults = {
        ITEMS_FILE: DEFAULT_ITEMS,
        NPCS_FILE: DEFAULT_NPCS,
        MONSTERS_FILE: DEFAULT_MONSTERS,
        RACES_FILE: DEFAULT_RACES,
        ENTITIES_FILE: DEFAULT_ENTITIES,
        JOBS_FILE: DEFAULT_JOB_DEFS,
        SIM_SETTINGS_FILE: DEFAULT_SIM_SETTINGS,
    }
    for path, value in defaults.items():
        if not path.exists():
            _write_json(path, value)


def load_item_defs() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(ITEMS_FILE, DEFAULT_ITEMS)
    out: List[Dict[str, object]] = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        key = str(it.get("key", "")).strip()
        display = str(it.get("display", "")).strip()
        if not key or not display:
            continue
        out.append({
            "key": key,
            "display": display,
            "is_craftable": bool(it.get("is_craftable", False)),
            "is_gatherable": bool(it.get("is_gatherable", False)),
            "craft_inputs": it.get("craft_inputs", {}) if isinstance(it.get("craft_inputs", {}), dict) else {},
            "craft_time": int(it.get("craft_time", 0)),
            "craft_fatigue": int(it.get("craft_fatigue", 0)),
            "craft_station": str(it.get("craft_station", "")),
            "craft_amount": int(it.get("craft_amount", 0)),
            "gather_time": int(it.get("gather_time", 0)),
            "gather_amount": int(it.get("gather_amount", 0)),
            "gather_fatigue": int(it.get("gather_fatigue", 0)),
            "gather_spot": str(it.get("gather_spot", "")),
        })
    return out or list(DEFAULT_ITEMS)


def save_item_defs(items: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(ITEMS_FILE, items)


def load_races() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(RACES_FILE, DEFAULT_RACES)
    out: List[Dict[str, object]] = []
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name", "")).strip()
        if not name:
            continue
        out.append({
            "name": name,
            "is_hostile": bool(r.get("is_hostile", False)),
            "str_bonus": int(r.get("str_bonus", 0)),
            "agi_bonus": int(r.get("agi_bonus", 0)),
            "hp_bonus": int(r.get("hp_bonus", 0)),
            "speed_bonus": float(r.get("speed_bonus", 0.0)),
        })
    return out or list(DEFAULT_RACES)


def save_races(races: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(RACES_FILE, races)


def _load_people(path: Path, fallback: List[Dict[str, object]]) -> List[Dict[str, object]]:
    raw = _read_json(path, fallback)
    races = {r["name"] for r in load_races()}
    out: List[Dict[str, object]] = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        race = str(it.get("race", "인간")).strip() or "인간"
        if race not in races:
            race = "인간"
        gender = str(it.get("gender", "기타")).strip() or "기타"
        if gender not in VALID_GENDERS:
            gender = "기타"
        job = str(it.get("job", "농부")).strip() or "농부"
        if job not in VALID_JOBS:
            job = "농부"
        out.append({"name": name, "race": race, "gender": gender, "age": int(it.get("age", 25)), "job": job})
    return out or list(fallback)


def load_npc_templates() -> List[Dict[str, object]]:
    ensure_data_files()
    return _load_people(NPCS_FILE, DEFAULT_NPCS)


def save_npc_templates(npcs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(NPCS_FILE, npcs)


def load_monster_templates() -> List[Dict[str, object]]:
    ensure_data_files()
    return _load_people(MONSTERS_FILE, DEFAULT_MONSTERS)


def save_monster_templates(monsters: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(MONSTERS_FILE, monsters)


def load_entities() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(ENTITIES_FILE, DEFAULT_ENTITIES)
    return raw if isinstance(raw, list) else list(DEFAULT_ENTITIES)


def save_entities(entities: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(ENTITIES_FILE, entities)


def load_job_defs() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(JOBS_FILE, DEFAULT_JOB_DEFS)
    return raw if isinstance(raw, list) else list(DEFAULT_JOB_DEFS)


def save_job_defs(job_defs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(JOBS_FILE, job_defs)


def load_sim_settings() -> Dict[str, float]:
    ensure_data_files()
    raw = _read_json(SIM_SETTINGS_FILE, DEFAULT_SIM_SETTINGS)
    out = dict(DEFAULT_SIM_SETTINGS)
    if isinstance(raw, dict):
        for k in out:
            try:
                out[k] = float(raw.get(k, out[k]))
            except Exception:
                pass
    return out


def save_sim_settings(settings: Dict[str, float]) -> None:
    ensure_data_files()
    _write_json(SIM_SETTINGS_FILE, settings)
