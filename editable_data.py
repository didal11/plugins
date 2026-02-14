#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Editable data store for non-developers.

이 모듈은 게임 데이터(아이템/NPC 템플릿)를 JSON으로 읽고 씁니다.
코드 수정 없이 UI 편집기(data_editor.py)에서 변경할 수 있습니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).parent / "data"
ITEMS_FILE = DATA_DIR / "items.json"
NPCS_FILE = DATA_DIR / "npcs.json"

DEFAULT_ITEMS: List[Dict[str, str]] = [
    {"key": "bread", "display": "빵"},
    {"key": "meat", "display": "고기"},
    {"key": "fish", "display": "생선"},
    {"key": "potion", "display": "포션"},
    {"key": "wood", "display": "목재"},
    {"key": "ore", "display": "광석"},
]

DEFAULT_NPCS: List[Dict[str, object]] = [
    {"name": "엘린", "race": "인간", "gender": "여", "age": 24, "height_cm": 167, "weight_kg": 56, "job": "모험가", "goal": "돈벌기"},
    {"name": "보른", "race": "드워프", "gender": "남", "age": 39, "height_cm": 146, "weight_kg": 76, "job": "대장장이", "goal": "명품 제작"},
    {"name": "마라", "race": "엘프", "gender": "여", "age": 31, "height_cm": 178, "weight_kg": 60, "job": "약사", "goal": "치유 연구"},
    {"name": "레오", "race": "인간", "gender": "남", "age": 28, "height_cm": 175, "weight_kg": 69, "job": "농부", "goal": "풍작"},
    {"name": "시안", "race": "엘프", "gender": "기타", "age": 26, "height_cm": 182, "weight_kg": 64, "job": "어부", "goal": "대어 잡기"},
]

VALID_JOBS = ["모험가", "농부", "어부", "대장장이", "약사"]


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ITEMS_FILE.exists():
        _write_json(ITEMS_FILE, DEFAULT_ITEMS)
    if not NPCS_FILE.exists():
        _write_json(NPCS_FILE, DEFAULT_NPCS)


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
        race = str(it.get("race", "인간")).strip() or "인간"
        gender = str(it.get("gender", "기타")).strip() or "기타"
        goal = str(it.get("goal", "돈벌기")).strip() or "돈벌기"
        job = str(it.get("job", "농부")).strip() or "농부"
        if job not in VALID_JOBS:
            job = "농부"
        if not name:
            continue
        try:
            age = int(it.get("age", 25))
            height_cm = int(it.get("height_cm", 170))
            weight_kg = int(it.get("weight_kg", 65))
        except Exception:
            continue
        out.append(
            {
                "name": name,
                "race": race,
                "gender": gender,
                "age": age,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "job": job,
                "goal": goal,
            }
        )
    return out or list(DEFAULT_NPCS)


def save_npc_templates(npcs: List[Dict[str, object]]) -> None:
    ensure_data_files()
    clean: List[Dict[str, object]] = []
    for it in npcs:
        try:
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
        except Exception:
            continue
    _write_json(NPCS_FILE, clean)
