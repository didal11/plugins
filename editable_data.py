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

DEFAULT_ITEMS: List[Dict[str, str]] = [
    {"key": "wheat", "display": "밀"},
    {"key": "bread", "display": "빵"},
    {"key": "fish", "display": "생선"},
    {"key": "meat", "display": "고기"},
    {"key": "herb", "display": "약초"},
    {"key": "potion", "display": "포션"},
    {"key": "wood", "display": "목재"},
    {"key": "lumber", "display": "제재목"},
    {"key": "ore", "display": "광석"},
    {"key": "ingot", "display": "주괴"},
    {"key": "hide", "display": "가죽"},
    {"key": "leather", "display": "가공가죽"},
    {"key": "artifact", "display": "유물"},
]

DEFAULT_JOB_DEFS: List[Dict[str, object]] = [
    {
        "job": "모험가",
        "primary_output": {"ore": 1, "wood": 1, "hide": 1},
        "input_need": {},
        "craft_output": {},
        "sell_items": ["ore", "wood", "hide", "artifact"],
        "sell_limit": 3,
    },
    {
        "job": "농부",
        "primary_output": {"wheat": 3},
        "input_need": {"wheat": 2},
        "craft_output": {"bread": 1},
        "sell_items": ["wheat", "bread"],
        "sell_limit": 4,
    },
    {
        "job": "어부",
        "primary_output": {"fish": 2},
        "input_need": {},
        "craft_output": {},
        "sell_items": ["fish"],
        "sell_limit": 3,
    },
    {
        "job": "대장장이",
        "primary_output": {"ore": 1},
        "input_need": {"ore": 2, "wood": 1},
        "craft_output": {"ingot": 1},
        "sell_items": ["ingot", "ore"],
        "sell_limit": 2,
    },
    {
        "job": "약사",
        "primary_output": {"herb": 2},
        "input_need": {"herb": 2},
        "craft_output": {"potion": 1},
        "sell_items": ["potion", "herb"],
        "sell_limit": 2,
    },
]

DEFAULT_SIM_SETTINGS: Dict[str, float] = {
    "npc_speed": 220.0,
    "hunger_gain_per_hour": 5.0,
    "fatigue_gain_per_hour": 4.0,
    "meal_hunger_restore": 30.0,
    "rest_fatigue_restore": 35.0,
    "potion_heal": 14.0,
}

DEFAULT_NPCS: List[Dict[str, object]] = [
    {"name": "엘린", "race": "인간", "gender": "여", "age": 24, "height_cm": 167, "weight_kg": 56, "job": "모험가", "goal": "돈벌기"},
    {"name": "보른", "race": "드워프", "gender": "남", "age": 39, "height_cm": 146, "weight_kg": 76, "job": "대장장이", "goal": "명품 제작"},
    {"name": "마라", "race": "엘프", "gender": "여", "age": 31, "height_cm": 178, "weight_kg": 60, "job": "약사", "goal": "치유 연구"},
    {"name": "레오", "race": "인간", "gender": "남", "age": 28, "height_cm": 175, "weight_kg": 69, "job": "농부", "goal": "풍작"},
    {"name": "시안", "race": "엘프", "gender": "기타", "age": 26, "height_cm": 182, "weight_kg": 64, "job": "어부", "goal": "대어 잡기"},
    {"name": "밀라", "race": "인간", "gender": "여", "age": 22, "height_cm": 164, "weight_kg": 54, "job": "농부", "goal": "가계 안정"},
    {"name": "도르", "race": "드워프", "gender": "남", "age": 41, "height_cm": 149, "weight_kg": 81, "job": "대장장이", "goal": "대량 생산"},
    {"name": "이리스", "race": "엘프", "gender": "여", "age": 29, "height_cm": 176, "weight_kg": 59, "job": "약사", "goal": "치유 보급"},
    {"name": "카이", "race": "인간", "gender": "남", "age": 27, "height_cm": 173, "weight_kg": 67, "job": "어부", "goal": "상단 납품"},
    {"name": "란", "race": "인간", "gender": "기타", "age": 25, "height_cm": 170, "weight_kg": 63, "job": "모험가", "goal": "유물 수집"},
    {"name": "노아", "race": "인간", "gender": "남", "age": 33, "height_cm": 171, "weight_kg": 70, "job": "농부", "goal": "곡물 상인"},
    {"name": "세라", "race": "엘프", "gender": "여", "age": 34, "height_cm": 179, "weight_kg": 62, "job": "약사", "goal": "특효약 개발"},
]

DEFAULT_MONSTERS: List[Dict[str, object]] = [
    {"name": "들개 고블린", "race": "고블린", "gender": "기타", "age": 8, "job": "모험가"},
    {"name": "늪지 슬라임", "race": "슬라임", "gender": "기타", "age": 3, "job": "모험가"},
    {"name": "산악 코볼트", "race": "코볼트", "gender": "기타", "age": 9, "job": "모험가"},
]

DEFAULT_RACES: List[Dict[str, object]] = [
    {"name": "인간", "is_hostile": False, "str_bonus": 0, "agi_bonus": 0, "hp_bonus": 0, "speed_bonus": 0.0},
    {"name": "엘프", "is_hostile": False, "str_bonus": 0, "agi_bonus": 1, "hp_bonus": 0, "speed_bonus": 0.05},
    {"name": "드워프", "is_hostile": False, "str_bonus": 1, "agi_bonus": 0, "hp_bonus": 2, "speed_bonus": -0.03},
]

DEFAULT_ENTITIES: List[Dict[str, object]] = []


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _normalize_item(it: Dict[str, object]) -> Dict[str, object]:
    key = str(it.get("key", "")).strip()
    display = str(it.get("display", "")).strip()
    if not key or not display:
        return {}
    return {
        "key": key,
        "display": display,
        "is_craftable": bool(it.get("is_craftable", False)),
        "is_gatherable": bool(it.get("is_gatherable", False)),
        "craft_inputs": it.get("craft_inputs", {}) if isinstance(it.get("craft_inputs", {}), dict) else {},
        "craft_time": max(0, int(it.get("craft_time", 0))),
        "craft_fatigue": max(0, int(it.get("craft_fatigue", 0))),
        "craft_station": str(it.get("craft_station", "")),
        "craft_amount": max(0, int(it.get("craft_amount", 0))),
        "gather_time": max(0, int(it.get("gather_time", 0))),
        "gather_amount": max(0, int(it.get("gather_amount", 0))),
        "gather_fatigue": max(0, int(it.get("gather_fatigue", 0))),
        "gather_spot": str(it.get("gather_spot", "")),
    }


def _normalize_race(row: Dict[str, object]) -> Dict[str, object]:
    name = str(row.get("name", "")).strip()
    if not name:
        return {}
    return {
        "name": name,
        "is_hostile": bool(row.get("is_hostile", False)),
        "str_bonus": int(row.get("str_bonus", 0)),
        "agi_bonus": int(row.get("agi_bonus", 0)),
        "hp_bonus": int(row.get("hp_bonus", 0)),
        "speed_bonus": float(row.get("speed_bonus", 0.0)),
    }


def _normalize_person(row: Dict[str, object], valid_races: set[str]) -> Dict[str, object]:
    name = str(row.get("name", "")).strip()
    if not name:
        return {}
    race = str(row.get("race", "인간")).strip() or "인간"
    if race not in valid_races:
        race = "인간"
    gender = str(row.get("gender", "기타")).strip() or "기타"
    if gender not in VALID_GENDERS:
        gender = "기타"
    job = str(row.get("job", "농부")).strip() or "농부"
    if job not in VALID_JOBS:
        job = "농부"
    return {
        "name": name,
        "race": race,
        "gender": gender,
        "age": max(1, int(row.get("age", 25))),
        "job": job,
    }


def _normalize_entity(row: Dict[str, object]) -> Dict[str, object]:
    kind = str(row.get("type", "workbench")).strip() or "workbench"
    if kind not in ("workbench", "resource"):
        return {}
    name = str(row.get("name", "")).strip()
    if not name:
        return {}
    out: Dict[str, object] = {
        "type": kind,
        "name": name,
        "x": int(row.get("x", 0)),
        "y": int(row.get("y", 0)),
    }
    if kind == "resource":
        out["stock"] = max(0, int(row.get("stock", 0)))
    return out


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
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        job = str(it.get("job", "농부")).strip() or "농부"
        if job not in VALID_JOBS:
            job = "농부"
        out.append(
            {
                "name": name,
                "race": str(it.get("race", "인간")).strip() or "인간",
                "gender": str(it.get("gender", "기타")).strip() or "기타",
                "age": int(it.get("age", 25)),
                "height_cm": int(it.get("height_cm", 170)),
                "weight_kg": int(it.get("weight_kg", 65)),
                "job": job,
                "goal": str(it.get("goal", "돈벌기")).strip() or "돈벌기",
            }
        )
    return out or list(DEFAULT_NPCS)


def load_monster_templates() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(MONSTERS_FILE, DEFAULT_MONSTERS)
    out: List[Dict[str, object]] = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "race": str(it.get("race", "고블린")).strip() or "고블린",
                "gender": str(it.get("gender", "기타")).strip() or "기타",
                "age": int(it.get("age", 5)),
                "job": "모험가",
            }
        )
    return out or list(DEFAULT_MONSTERS)


def save_npc_templates(npcs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    clean: List[Dict[str, object]] = []
    for it in npcs:
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        job = str(it.get("job", "농부")).strip() or "농부"
        if job not in VALID_JOBS:
            job = "농부"
        clean.append(
            {
                "name": name,
                "race": str(it.get("race", "인간")).strip() or "인간",
                "gender": str(it.get("gender", "기타")).strip() or "기타",
                "age": int(it.get("age", 25)),
                "height_cm": int(it.get("height_cm", 170)),
                "weight_kg": int(it.get("weight_kg", 65)),
                "job": job,
                "goal": str(it.get("goal", "돈벌기")).strip() or "돈벌기",
            }
        )
    _write_json(NPCS_FILE, clean)


def save_monster_templates(monsters: List[Dict[str, object]]) -> None:
    ensure_data_files()
    clean: List[Dict[str, object]] = []
    for it in monsters:
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        clean.append(
            {
                "name": name,
                "race": str(it.get("race", "고블린")).strip() or "고블린",
                "gender": str(it.get("gender", "기타")).strip() or "기타",
                "age": int(it.get("age", 5)),
                "job": "모험가",
            }
        )
    _write_json(MONSTERS_FILE, clean)


def load_job_defs() -> List[Dict[str, object]]:
    ensure_data_files()
    try:
        raw = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return list(DEFAULT_JOB_DEFS)
    out: List[Dict[str, object]] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        job = str(row.get("job", "")).strip()
        if job not in VALID_JOBS:
            continue
        out.append(
            {
                "job": job,
                "primary_output": row.get("primary_output", {}),
                "input_need": row.get("input_need", {}),
                "craft_output": row.get("craft_output", {}),
                "sell_items": row.get("sell_items", []),
                "sell_limit": int(row.get("sell_limit", 3)),
            }
        )
    return out or list(DEFAULT_JOB_DEFS)


def save_job_defs(job_defs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    clean: List[Dict[str, object]] = []
    for row in job_defs:
        job = str(row.get("job", "")).strip()
        if job not in VALID_JOBS:
            continue
        clean.append(
            {
                "job": job,
                "primary_output": row.get("primary_output", {}),
                "input_need": row.get("input_need", {}),
                "craft_output": row.get("craft_output", {}),
                "sell_items": row.get("sell_items", []),
                "sell_limit": int(row.get("sell_limit", 3)),
            }
        )
    _write_json(JOBS_FILE, clean)


def load_sim_settings() -> Dict[str, float]:
    ensure_data_files()
    try:
        raw = json.loads(SIM_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_SIM_SETTINGS)
    out = dict(DEFAULT_SIM_SETTINGS)
    if isinstance(raw, dict):
        for k in out.keys():
            try:
                out[k] = float(raw.get(k, out[k]))
            except Exception:
                pass
    return out


def save_sim_settings(settings: Dict[str, float]) -> None:
    ensure_data_files()
    out = dict(DEFAULT_SIM_SETTINGS)
    for k in out.keys():
        try:
            out[k] = float(settings.get(k, out[k]))
        except Exception:
            pass
    _write_json(SIM_SETTINGS_FILE, out)
