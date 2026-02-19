#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import orjson
import re
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).parent / "data"
MAP_FILE = DATA_DIR / "map.ldtk"
NPCS_FILE = DATA_DIR / "npcs.json"
MONSTERS_FILE = DATA_DIR / "monsters.json"
RACES_FILE = DATA_DIR / "races.json"
JOBS_FILE = DATA_DIR / "jobs.json"
SIM_SETTINGS_FILE = DATA_DIR / "sim_settings.json"

VALID_JOBS = ["모험가", "농부", "어부", "대장장이", "약사"]
VALID_GENDERS = ["남", "여", "기타"]

DEFAULT_ITEMS: List[Dict[str, object]] = [
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
    {"key": "tool", "display": "도구"},
]

DEFAULT_JOB_DEFS: List[Dict[str, object]] = [
    {"job": "모험가", "work_actions": ["게시판확인", "탐색", "약초채집", "벌목", "채광", "동물사냥", "몬스터사냥"]},
    {"job": "농부", "work_actions": ["농사"]},
    {"job": "어부", "work_actions": ["낚시"]},
    {"job": "대장장이", "work_actions": ["제련", "도구제작"]},
    {"job": "약사", "work_actions": ["약 제조"]},
]

DEFAULT_ACTION_DEFS: List[Dict[str, object]] = [
    {"name": "게시판확인", "duration_minutes": 10, "required_tools": [], "required_entity": "guild_board", "schedulable": False, "interruptible": True},
    {"name": "게시판보고", "duration_minutes": 10, "required_tools": [], "required_entity": "guild_board", "schedulable": False, "interruptible": True},
    {"name": "탐색", "duration_minutes": 10, "required_tools": ["도구"], "required_entity": "", "schedulable": True, "interruptible": True},
]

DEFAULT_SIM_SETTINGS: Dict[str, float] = {
    "npc_speed": 220.0,
    "hunger_gain_per_tick": 5.0 / 6.0,
    "fatigue_gain_per_tick": 4.0 / 6.0,
    "meal_hunger_restore": 30.0,
    "rest_fatigue_restore": 35.0,
    "potion_heal": 14.0,
    "explore_duration_ticks": 6,
}


DEFAULT_NPCS: List[Dict[str, object]] = [
    {"name": "엘린", "race": "인간", "gender": "여", "age": 24, "job": "모험가"},
    {"name": "보른", "race": "드워프", "gender": "남", "age": 39, "job": "대장장이"},
    {"name": "마라", "race": "엘프", "gender": "여", "age": 31, "job": "약사"},
]
DEFAULT_MONSTERS: List[Dict[str, object]] = [
    {"name": "들개 고블린", "race": "고블린", "gender": "기타", "age": 8, "job": "모험가"},
    {"name": "늪지 슬라임", "race": "슬라임", "gender": "기타", "age": 3, "job": "모험가"},
]
DEFAULT_RACES: List[Dict[str, object]] = [
    {"name": "인간", "is_hostile": False, "str_bonus": 0, "agi_bonus": 0, "hp_bonus": 0, "speed_bonus": 0.0},
    {"name": "엘프", "is_hostile": False, "str_bonus": 0, "agi_bonus": 1, "hp_bonus": 0, "speed_bonus": 0.05},
    {"name": "드워프", "is_hostile": False, "str_bonus": 1, "agi_bonus": 0, "hp_bonus": 2, "speed_bonus": -0.03},
]


def _write_json(path: Path, obj: object) -> None:
    path.write_bytes(orjson.dumps(obj, option=orjson.OPT_INDENT_2))


def _read_json(path: Path, fallback: object) -> object:
    try:
        return orjson.loads(path.read_bytes())
    except Exception:
        return fallback


def _seed_if_empty(path: Path, rows: List[Dict[str, object]], defaults: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if rows:
        return rows
    seeded = list(defaults)
    _write_json(path, seeded)
    return seeded


def _job_names_from_raw(raw: object) -> List[str]:
    names: List[str] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        job_name = str(row.get("job", "")).strip()
        if not job_name or job_name in names:
            continue
        names.append(job_name)
    return names


def load_job_names() -> List[str]:
    """jobs.json의 직업명을 읽어 UI/검증에 공통으로 사용한다."""
    ensure_data_files()
    raw = _read_json(JOBS_FILE, DEFAULT_JOB_DEFS)
    names = _job_names_from_raw(raw)
    if names:
        return names
    return list(VALID_JOBS)


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    defaults = {
        NPCS_FILE: DEFAULT_NPCS,
        MONSTERS_FILE: DEFAULT_MONSTERS,
        RACES_FILE: DEFAULT_RACES,
        JOBS_FILE: DEFAULT_JOB_DEFS,
        SIM_SETTINGS_FILE: DEFAULT_SIM_SETTINGS,
    }
    for path, value in defaults.items():
        if not path.exists():
            _write_json(path, value)


def _normalize_item_key(identifier: str) -> str:
    key = str(identifier).strip()
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).replace(" ", "_").replace("-", "_")
    return key.lower()


def _entity_default_name(entity_def: Dict[str, object]) -> str:
    field_defs = entity_def.get("fieldDefs", [])
    if not isinstance(field_defs, list):
        return ""
    for field in field_defs:
        if not isinstance(field, dict):
            continue
        if str(field.get("identifier", "")).strip() != "name":
            continue
        default_override = field.get("defaultOverride")
        if not isinstance(default_override, dict):
            return ""
        params = default_override.get("params", [])
        if not isinstance(params, list) or not params:
            return ""
        return str(params[0]).strip()
    return ""


def load_item_defs() -> List[Dict[str, object]]:
    if not MAP_FILE.exists():
        return list(DEFAULT_ITEMS)
    raw = _read_json(MAP_FILE, {})
    defs = raw.get("defs", {}) if isinstance(raw, dict) else {}
    entities = defs.get("entities", []) if isinstance(defs, dict) else []
    out: List[Dict[str, object]] = []
    seen_keys: set[str] = set()
    for entity_def in entities if isinstance(entities, list) else []:
        if not isinstance(entity_def, dict):
            continue
        tags = {
            str(tag).strip().lower()
            for tag in entity_def.get("tags", [])
            if str(tag).strip()
        } if isinstance(entity_def.get("tags", []), list) else set()
        if "item" not in tags:
            continue
        identifier = str(entity_def.get("identifier", "")).strip()
        key = _normalize_item_key(identifier)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        display = _entity_default_name(entity_def) or identifier or key
        out.append({"key": key, "display": display})
    return out or list(DEFAULT_ITEMS)


def load_npc_templates() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(NPCS_FILE, DEFAULT_NPCS)
    valid_jobs = set(load_job_names())
    out: List[Dict[str, object]] = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        job = str(it.get("job", "농부")).strip() or "농부"
        if job not in valid_jobs:
            job = "농부"
        row: Dict[str, object] = {"name": name, "race": str(it.get("race", "인간")).strip() or "인간", "gender": str(it.get("gender", "기타")).strip() or "기타", "age": int(it.get("age", 25)), "job": job}
        if "height_cm" in it:
            row["height_cm"] = int(it.get("height_cm", 170))
        if "weight_kg" in it:
            row["weight_kg"] = int(it.get("weight_kg", 65))
        if "goal" in it:
            row["goal"] = str(it.get("goal", ""))
        out.append(row)
    return out


def save_npc_templates(npcs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(NPCS_FILE, npcs)


def load_monster_templates() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(MONSTERS_FILE, DEFAULT_MONSTERS)
    valid_jobs = set(load_job_names())
    out: List[Dict[str, object]] = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        job = str(it.get("job", "모험가")).strip() or "모험가"
        if job not in valid_jobs:
            job = "모험가"
        out.append({"name": name, "race": str(it.get("race", "고블린")).strip() or "고블린", "gender": str(it.get("gender", "기타")).strip() or "기타", "age": int(it.get("age", 5)), "job": job})
    return out


def save_monster_templates(monsters: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(MONSTERS_FILE, monsters)


def load_races() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(RACES_FILE, DEFAULT_RACES)
    out: List[Dict[str, object]] = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        out.append({"name": name, "is_hostile": bool(it.get("is_hostile", False)), "str_bonus": int(it.get("str_bonus", 0)), "agi_bonus": int(it.get("agi_bonus", 0)), "hp_bonus": int(it.get("hp_bonus", 0)), "speed_bonus": float(it.get("speed_bonus", 0.0))})
    return _seed_if_empty(RACES_FILE, out, DEFAULT_RACES)


def load_job_defs() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(JOBS_FILE, DEFAULT_JOB_DEFS)
    out: List[Dict[str, object]] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        job = str(row.get("job", "")).strip()
        if not job:
            continue
        actions = row.get("work_actions", []) if isinstance(row.get("work_actions", []), list) else []
        out.append({"job": job, "work_actions": [str(x).strip() for x in actions if str(x).strip()]})
    return _seed_if_empty(JOBS_FILE, out, DEFAULT_JOB_DEFS)


def load_action_defs() -> List[Dict[str, object]]:
    if not MAP_FILE.exists():
        return list(DEFAULT_ACTION_DEFS)
    raw = _read_json(MAP_FILE, {})
    defs = raw.get("defs", {}) if isinstance(raw, dict) else {}
    entities = defs.get("entities", []) if isinstance(defs, dict) else []
    out: List[Dict[str, object]] = []
    for entity_def in entities if isinstance(entities, list) else []:
        if not isinstance(entity_def, dict):
            continue
        tags = {
            str(tag).strip().lower()
            for tag in entity_def.get("tags", [])
            if str(tag).strip()
        } if isinstance(entity_def.get("tags", []), list) else set()
        if "action" not in tags:
            continue

        fields: Dict[str, object] = {}
        for field in entity_def.get("fieldDefs", []) if isinstance(entity_def.get("fieldDefs", []), list) else []:
            if not isinstance(field, dict):
                continue
            identifier = str(field.get("identifier", "")).strip()
            if not identifier:
                continue
            default_override = field.get("defaultOverride")
            value: object = None
            if isinstance(default_override, dict):
                params = default_override.get("params", [])
                if isinstance(params, list) and params:
                    value = params[0]
            fields[identifier] = value

        name = str(fields.get("name", "")).strip()
        if not name:
            continue
        required_tools_raw = str(fields.get("required_tools", "")).strip()
        required_tools = [part.strip() for part in required_tools_raw.split(",") if part.strip()]
        out.append({
            "name": name,
            "duration_minutes": max(10, int(fields.get("duration_minutes", 10) or 10) // 10 * 10),
            "required_tools": required_tools,
            "required_entity": str(fields.get("required_entity", "")).strip(),
            "schedulable": bool(fields.get("schedulable", True)),
            "interruptible": bool(fields.get("interruptible", True)),
        })
    return out or list(DEFAULT_ACTION_DEFS)

def save_job_defs(job_defs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(JOBS_FILE, job_defs)


def load_sim_settings() -> Dict[str, float]:
    ensure_data_files()
    raw = _read_json(SIM_SETTINGS_FILE, DEFAULT_SIM_SETTINGS)
    out = dict(DEFAULT_SIM_SETTINGS)
    if isinstance(raw, dict):
        if "hunger_gain_per_tick" not in raw and "hunger_gain_per_hour" in raw:
            raw["hunger_gain_per_tick"] = float(raw.get("hunger_gain_per_hour", 5.0)) / 6.0
        if "fatigue_gain_per_tick" not in raw and "fatigue_gain_per_hour" in raw:
            raw["fatigue_gain_per_tick"] = float(raw.get("fatigue_gain_per_hour", 4.0)) / 6.0
        for k in out:
            try:
                out[k] = float(raw.get(k, out[k])) if k != "explore_duration_ticks" else int(raw.get(k, out[k]))
            except Exception:
                pass
    if int(out.get("explore_duration_ticks", 6)) not in (6, 12, 18):
        out["explore_duration_ticks"] = 6
    return out


def save_sim_settings(settings: Dict[str, float]) -> None:
    ensure_data_files()
    out = dict(DEFAULT_SIM_SETTINGS)
    for k in out:
        try:
            out[k] = float(settings.get(k, out[k])) if k != "explore_duration_ticks" else int(settings.get(k, out[k]))
        except Exception:
            pass
    if int(out.get("explore_duration_ticks", 6)) not in (6, 12, 18):
        out["explore_duration_ticks"] = 6
    _write_json(SIM_SETTINGS_FILE, out)


def load_all_data() -> Dict[str, object]:
    """단일 진입점: 에디터/시뮬레이터가 같은 로더를 사용."""
    return {
        "items": load_item_defs(),
        "npcs": load_npc_templates(),
        "monsters": load_monster_templates(),
        "races": load_races(),
        "jobs": load_job_defs(),
        "actions": load_action_defs(),
        "sim": load_sim_settings(),
    }
