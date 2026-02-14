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
ACTIONS_FILE = DATA_DIR / "actions.json"
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
    {"job": "모험가", "work_actions": ["약초채집", "벌목", "채광", "동물사냥", "몬스터사냥"]},
    {"job": "농부", "work_actions": ["농사"]},
    {"job": "어부", "work_actions": ["낚시"]},
    {"job": "대장장이", "work_actions": ["제련", "도구제작"]},
    {"job": "약사", "work_actions": ["약 제조"]},
]

DEFAULT_ACTION_DEFS: List[Dict[str, object]] = [
    {"name": "농사", "duration_hours": 1, "required_tools": ["도구"], "outputs": {"wheat": {"min": 2, "max": 4}}, "fatigue": 14, "hunger": 8},
    {"name": "낚시", "duration_hours": 1, "required_tools": ["도구"], "outputs": {"fish": {"min": 1, "max": 3}}, "fatigue": 13, "hunger": 7},
    {"name": "제련", "duration_hours": 2, "required_tools": ["도구"], "outputs": {"ingot": {"min": 1, "max": 3}}, "fatigue": 12, "hunger": 7},
    {"name": "도구제작", "duration_hours": 1, "required_tools": ["도구"], "outputs": {"tool": {"min": 1, "max": 1}}, "fatigue": 11, "hunger": 6},
    {"name": "약 제조", "duration_hours": 1, "required_tools": ["도구"], "outputs": {"potion": {"min": 1, "max": 2}}, "fatigue": 10, "hunger": 6},
    {"name": "약초채집", "duration_hours": 1, "required_tools": ["도구"], "outputs": {"herb": {"min": 2, "max": 4}}, "fatigue": 11, "hunger": 7},
    {"name": "벌목", "duration_hours": 2, "required_tools": ["도구"], "outputs": {"wood": {"min": 1, "max": 3}}, "fatigue": 15, "hunger": 9},
    {"name": "채광", "duration_hours": 2, "required_tools": ["도구"], "outputs": {"ore": {"min": 1, "max": 3}}, "fatigue": 16, "hunger": 9},
    {"name": "동물사냥", "duration_hours": 3, "required_tools": ["도구"], "outputs": {"meat": {"min": 1, "max": 2}, "hide": {"min": 1, "max": 1}}, "fatigue": 16, "hunger": 10},
    {"name": "몬스터사냥", "duration_hours": 3, "required_tools": ["도구"], "outputs": {"artifact": {"min": 1, "max": 1}, "ore": {"min": 0, "max": 1}}, "fatigue": 18, "hunger": 11},
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
DEFAULT_ENTITIES: List[Dict[str, object]] = []


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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
        ITEMS_FILE: DEFAULT_ITEMS,
        NPCS_FILE: DEFAULT_NPCS,
        MONSTERS_FILE: DEFAULT_MONSTERS,
        RACES_FILE: DEFAULT_RACES,
        ENTITIES_FILE: DEFAULT_ENTITIES,
        JOBS_FILE: DEFAULT_JOB_DEFS,
        ACTIONS_FILE: DEFAULT_ACTION_DEFS,
        SIM_SETTINGS_FILE: DEFAULT_SIM_SETTINGS,
    }
    for path, value in defaults.items():
        if not path.exists():
            _write_json(path, value)


def _normalize_entity(row: Dict[str, object]) -> Dict[str, object]:
    kind = str(row.get("type", "workbench")).strip() or "workbench"
    if kind not in ("workbench", "resource"):
        return {}
    name = str(row.get("name", "")).strip()
    if not name:
        return {}
    out: Dict[str, object] = {"type": kind, "name": name, "x": int(row.get("x", 0)), "y": int(row.get("y", 0))}
    if kind == "resource":
        out["stock"] = max(0, int(row.get("stock", 0)))
    return out


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
    return _seed_if_empty(ITEMS_FILE, out, DEFAULT_ITEMS)


def save_item_defs(items: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(ITEMS_FILE, items)


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


def load_entities() -> List[Dict[str, object]]:
    ensure_data_files()
    raw = _read_json(ENTITIES_FILE, DEFAULT_ENTITIES)
    out: List[Dict[str, object]] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        norm = _normalize_entity(row)
        if norm:
            out.append(norm)
    return out


def save_entities(entities: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(ENTITIES_FILE, [e for e in (_normalize_entity(x) for x in entities if isinstance(x, dict)) if e])


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
    ensure_data_files()
    raw = _read_json(ACTIONS_FILE, DEFAULT_ACTION_DEFS)
    item_keys = {str(it.get("key", "")).strip() for it in load_item_defs() if isinstance(it, dict)}
    out: List[Dict[str, object]] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        outputs_raw = row.get("outputs", {}) if isinstance(row.get("outputs", {}), dict) else {}
        outputs = {k: v for k, v in outputs_raw.items() if str(k).strip() in item_keys}
        out.append({
            "name": name,
            "duration_hours": max(1, int(row.get("duration_hours", 1))),
            "required_tools": ["도구"],
            "outputs": outputs,
            "fatigue": int(row.get("fatigue", 12)),
            "hunger": int(row.get("hunger", 8)),
        })
    return _seed_if_empty(ACTIONS_FILE, out, DEFAULT_ACTION_DEFS)




def save_action_defs(action_defs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    _write_json(ACTIONS_FILE, action_defs)

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
    out = dict(DEFAULT_SIM_SETTINGS)
    for k in out:
        try:
            out[k] = float(settings.get(k, out[k]))
        except Exception:
            pass
    _write_json(SIM_SETTINGS_FILE, out)


def load_all_data() -> Dict[str, object]:
    """단일 진입점: 에디터/시뮬레이터가 같은 로더를 사용."""
    return {
        "items": load_item_defs(),
        "npcs": load_npc_templates(),
        "monsters": load_monster_templates(),
        "races": load_races(),
        "entities": load_entities(),
        "jobs": load_job_defs(),
        "actions": load_action_defs(),
        "sim": load_sim_settings(),
    }
