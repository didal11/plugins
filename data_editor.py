#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from editable_data import (
    VALID_GENDERS,
    load_item_defs,
    load_job_defs,
    load_action_defs,
    load_job_names,
    load_monster_templates,
    load_npc_templates,
    load_races,
    load_sim_settings,
    save_job_defs,
    save_monster_templates,
    save_npc_templates,
    save_sim_settings,
)

DATA_DIR = Path(__file__).parent / "data"
COMBAT_FILE = DATA_DIR / "combat.json"
RACES_FILE = DATA_DIR / "races.json"


class EditorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("판타지 마을 데이터 편집기")
        self.geometry("1100x760")

        self.items = load_item_defs()
        self.npcs = load_npc_templates()
        self.monsters = load_monster_templates()
        self.races = load_races()
        self.jobs = load_job_defs()
        self.actions = load_action_defs()
        self.job_names = load_job_names()
        self.sim = load_sim_settings()
        self.combat = self._load_combat_settings()
        self.person_job_boxes: list[ttk.Combobox] = []

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.item_tab = ttk.Frame(notebook)
        self.npc_tab = ttk.Frame(notebook)
        self.monster_tab = ttk.Frame(notebook)
        self.race_tab = ttk.Frame(notebook)
        self.job_tab = ttk.Frame(notebook)
        self.action_tab = ttk.Frame(notebook)
        self.sim_tab = ttk.Frame(notebook)
        self.combat_tab = ttk.Frame(notebook)

        notebook.add(self.item_tab, text="아이템")
        notebook.add(self.npc_tab, text="NPC")
        notebook.add(self.monster_tab, text="몬스터")
        notebook.add(self.race_tab, text="종족")
        notebook.add(self.job_tab, text="직업")
        notebook.add(self.action_tab, text="행동")
        notebook.add(self.sim_tab, text="시뮬 설정")
        notebook.add(self.combat_tab, text="전투")

        self._build_item_tab()
        self._build_person_tab(self.npc_tab, mode="npc")
        self._build_person_tab(self.monster_tab, mode="monster")
        self._build_race_tab()
        self._build_job_tab()
        self._build_action_tab()
        self._build_sim_tab()
        self._build_combat_tab()
        self._refresh_job_choices()

    def _default_job_for_mode(self, mode: str) -> str:
        if self.job_names:
            return self.job_names[0]
        return "농부" if mode == "npc" else "모험가"

    def _refresh_job_choices(self) -> None:
        self.job_names = load_job_names()
        for box in self.person_job_boxes:
            box.configure(values=self.job_names)
            if box.get().strip() and box.get().strip() in self.job_names:
                continue
            box.set("")
        if hasattr(self, "job_name"):
            self.job_name.configure(values=self.job_names)
            if self.job_name.get().strip() and self.job_name.get().strip() in self.job_names:
                return
            self.job_name.set(self.job_names[0] if self.job_names else "")

    def _race_names(self) -> list[str]:
        names = [str(r.get("name", "")).strip() for r in self.races]
        return [n for n in names if n]

    def _load_combat_settings(self) -> dict[str, object]:
        default = {
            "hostile_race": "적대",
            "engage_range_tiles": 2,
            "base_hit_chance": 0.75,
            "agility_evasion_scale": 0.015,
            "min_damage": 5,
            "max_damage": 14,
            "strength_damage_scale": 0.45,
            "adventurer_attack_bonus": 0.1,
            "hostile_attack_bonus": 0.05,
        }
        if not COMBAT_FILE.exists():
            COMBAT_FILE.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
            return default
        try:
            raw = json.loads(COMBAT_FILE.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else dict(default)
        except Exception:
            return dict(default)

    # ---------- Item tab ----------
    def _build_item_tab(self) -> None:
        left = ttk.Frame(self.item_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.item_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.item_list = tk.Listbox(left, width=34, height=30, exportselection=False)
        self.item_list.pack(fill="y")
        self.item_list.bind("<<ListboxSelect>>", self._on_item_select)
        for row in self.items:
            self.item_list.insert("end", f"{row.get('key', '')} ({row.get('display', '')})")

        ttk.Label(right, text="아이템 키").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(right, text="표시 이름").grid(row=1, column=0, sticky="w", pady=2)
        self.item_key = ttk.Entry(right, width=44)
        self.item_display = ttk.Entry(right, width=44)
        self.item_key.grid(row=0, column=1, sticky="w", pady=2)
        self.item_display.grid(row=1, column=1, sticky="w", pady=2)
        self.item_key.configure(state="readonly")
        self.item_display.configure(state="readonly")
        ttk.Label(
            right,
            text="아이템 정의는 map.ldtk 의 item 태그 엔티티에서 자동 로드됩니다.",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 2))

    def _on_item_select(self, _=None) -> None:
        sel = self.item_list.curselection()
        if not sel:
            return
        row = self.items[sel[0]]
        self.item_key.configure(state="normal")
        self.item_key.delete(0, "end")
        self.item_key.insert(0, str(row.get("key", "")))
        self.item_key.configure(state="readonly")
        self.item_display.configure(state="normal")
        self.item_display.delete(0, "end")
        self.item_display.insert(0, str(row.get("display", "")))
        self.item_display.configure(state="readonly")

    # ---------- NPC / Monster tabs ----------
    def _build_person_tab(self, tab: ttk.Frame, mode: str) -> None:
        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        data = self.npcs if mode == "npc" else self.monsters
        lb = tk.Listbox(left, width=36, height=30, exportselection=False)
        lb.pack(fill="y")
        for row in data:
            lb.insert("end", f"{row.get('name','')} ({row.get('race','')}/{row.get('job','')})")

        entries: dict[str, tk.Widget] = {}
        fields = [("name", "이름"), ("race", "종족"), ("gender", "성별"), ("age", "나이")]
        if mode == "npc":
            fields += [("height_cm", "키(cm)"), ("weight_kg", "몸무게(kg)"), ("goal", "목표")]
        fields += [("job", "직업")]

        for i, (key, label) in enumerate(fields):
            ttk.Label(right, text=label).grid(row=i, column=0, sticky="w", pady=2)
            if key == "gender":
                widget = ttk.Combobox(right, values=VALID_GENDERS, state="readonly", width=40)
            elif key == "job":
                widget = ttk.Combobox(right, values=self.job_names, state="readonly", width=40)
                self.person_job_boxes.append(widget)
            elif key == "race":
                widget = ttk.Combobox(right, values=self._race_names(), state="readonly", width=40)
            else:
                widget = ttk.Entry(right, width=43)
            widget.grid(row=i, column=1, sticky="w", pady=2)
            entries[key] = widget

        def on_select(_=None) -> None:
            sel = lb.curselection()
            if not sel:
                return
            row = data[sel[0]]
            for key, widget in entries.items():
                value = str(row.get(key, ""))
                if isinstance(widget, ttk.Combobox):
                    widget.set(value)
                else:
                    widget.delete(0, "end")
                    widget.insert(0, value)

        lb.bind("<<ListboxSelect>>", on_select)

        def from_form() -> dict[str, object] | None:
            try:
                row: dict[str, object] = {
                    "name": entries["name"].get().strip(),
                    "race": entries["race"].get().strip() or ("인간" if mode == "npc" else "고블린"),
                    "gender": entries["gender"].get().strip() or "기타",
                    "age": int(entries["age"].get().strip() or "20"),
                    "job": entries["job"].get().strip() or self._default_job_for_mode(mode),
                }
                if mode == "npc":
                    row["height_cm"] = int(entries["height_cm"].get().strip() or "170")
                    row["weight_kg"] = int(entries["weight_kg"].get().strip() or "65")
                    row["goal"] = entries["goal"].get().strip()
                return row
            except ValueError:
                messagebox.showwarning("경고", "나이/신체 수치는 숫자로 입력하세요.")
                return None

        def add_row() -> None:
            row = from_form()
            if not row or not row.get("name"):
                return
            data.append(row)
            lb.insert("end", f"{row['name']} ({row['race']}/{row['job']})")

        def update_row() -> None:
            sel = lb.curselection()
            if not sel:
                return
            row = from_form()
            if not row or not row.get("name"):
                return
            idx = sel[0]
            data[idx] = row
            lb.delete(idx)
            lb.insert(idx, f"{row['name']} ({row['race']}/{row['job']})")

        def delete_row() -> None:
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            lb.delete(idx)
            data.pop(idx)

        def save_rows() -> None:
            sel = lb.curselection()
            if sel:
                row = from_form()
                if not row or not row.get("name"):
                    return
                idx = sel[0]
                data[idx] = row
                lb.delete(idx)
                lb.insert(idx, f"{row['name']} ({row['race']}/{row['job']})")
                lb.selection_set(idx)
                lb.activate(idx)
            if mode == "npc":
                save_npc_templates(data)
                messagebox.showinfo("저장 완료", "NPC 데이터를 저장했습니다.")
            else:
                save_monster_templates(data)
                messagebox.showinfo("저장 완료", "몬스터 데이터를 저장했습니다.")

        btns = ttk.Frame(right)
        btns.grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btns, text="추가", command=add_row).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=update_row).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=delete_row).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=save_rows).pack(side="left", padx=3)

    # ---------- Race tab ----------
    def _build_race_tab(self) -> None:
        left = ttk.Frame(self.race_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.race_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.race_list = tk.Listbox(left, width=30, height=28, exportselection=False)
        self.race_list.pack(fill="y")
        self.race_list.bind("<<ListboxSelect>>", self._on_race_select)
        for row in self.races:
            self.race_list.insert("end", str(row.get("name", "")))

        ttk.Label(right, text="이름").grid(row=0, column=0, sticky="w", pady=2)
        self.race_name = ttk.Entry(right, width=44)
        self.race_name.grid(row=0, column=1, sticky="w", pady=2)

        self.race_is_hostile = tk.BooleanVar(value=False)
        ttk.Checkbutton(right, text="적대 종족", variable=self.race_is_hostile).grid(row=1, column=1, sticky="w", pady=2)

        self.race_numbers: dict[str, ttk.Entry] = {}
        labels = [
            ("str_bonus", "힘 보너스"),
            ("agi_bonus", "민첩 보너스"),
            ("hp_bonus", "체력 보너스"),
            ("speed_bonus", "속도 보너스"),
        ]
        for idx, (key, label) in enumerate(labels, start=2):
            ttk.Label(right, text=label).grid(row=idx, column=0, sticky="w", pady=2)
            entry = ttk.Entry(right, width=44)
            entry.grid(row=idx, column=1, sticky="w", pady=2)
            self.race_numbers[key] = entry

        btns = ttk.Frame(right)
        btns.grid(row=6, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btns, text="추가", command=self._add_race).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_race).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_race).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=self._save_races).pack(side="left", padx=3)

    def _race_from_form(self) -> dict[str, object] | None:
        try:
            return {
                "name": self.race_name.get().strip(),
                "is_hostile": bool(self.race_is_hostile.get()),
                "str_bonus": int(self.race_numbers["str_bonus"].get().strip() or "0"),
                "agi_bonus": int(self.race_numbers["agi_bonus"].get().strip() or "0"),
                "hp_bonus": int(self.race_numbers["hp_bonus"].get().strip() or "0"),
                "speed_bonus": float(self.race_numbers["speed_bonus"].get().strip() or "0"),
            }
        except ValueError:
            messagebox.showwarning("경고", "종족 보너스 수치를 확인하세요.")
            return None

    def _on_race_select(self, _=None) -> None:
        sel = self.race_list.curselection()
        if not sel:
            return
        row = self.races[sel[0]]
        self.race_name.delete(0, "end")
        self.race_name.insert(0, str(row.get("name", "")))
        self.race_is_hostile.set(bool(row.get("is_hostile", False)))
        for key, entry in self.race_numbers.items():
            entry.delete(0, "end")
            entry.insert(0, str(row.get(key, 0)))

    def _add_race(self) -> None:
        row = self._race_from_form()
        if not row or not row.get("name"):
            return
        self.races.append(row)
        self.race_list.insert("end", str(row["name"]))

    def _update_race(self) -> None:
        sel = self.race_list.curselection()
        if not sel:
            return
        row = self._race_from_form()
        if not row or not row.get("name"):
            return
        idx = sel[0]
        self.races[idx] = row
        self.race_list.delete(idx)
        self.race_list.insert(idx, str(row["name"]))

    def _delete_race(self) -> None:
        sel = self.race_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.race_list.delete(idx)
        self.races.pop(idx)

    def _save_races(self) -> None:
        RACES_FILE.write_text(json.dumps(self.races, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("저장 완료", "종족 데이터를 저장했습니다.")

    # ---------- Job tab ----------
    def _build_job_tab(self) -> None:
        left = ttk.Frame(self.job_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.job_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.job_list = tk.Listbox(left, width=28, height=25, exportselection=False)
        self.job_list.pack(fill="y")
        self.job_list.bind("<<ListboxSelect>>", self._on_job_select)
        for row in self.jobs:
            self.job_list.insert("end", str(row.get("job", "")))

        ttk.Label(right, text="직업").grid(row=0, column=0, sticky="w", pady=2)
        self.job_name = ttk.Combobox(right, values=self.job_names, state="readonly", width=40)
        self.job_name.grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(right, text="가능한 일(쉼표)").grid(row=1, column=0, sticky="w", pady=2)
        self.job_work_actions = ttk.Entry(right, width=43)
        self.job_work_actions.grid(row=1, column=1, sticky="w", pady=2)

        btns = ttk.Frame(right)
        btns.grid(row=2, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btns, text="추가", command=self._add_job).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_job).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_job).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=self._save_jobs).pack(side="left", padx=3)

    def _on_job_select(self, _=None) -> None:
        sel = self.job_list.curselection()
        if not sel:
            return
        row = self.jobs[sel[0]]
        self.job_name.set(str(row.get("job", "")))
        self.job_work_actions.delete(0, "end")
        self.job_work_actions.insert(0, ",".join([str(x) for x in row.get("work_actions", [])]))

    def _job_from_form(self) -> dict[str, object] | None:
        name = self.job_name.get().strip()
        if not name:
            messagebox.showwarning("경고", "직업명을 선택하세요.")
            return None
        actions = [x.strip() for x in self.job_work_actions.get().split(",") if x.strip()]
        return {"job": name, "work_actions": actions}

    def _add_job(self) -> None:
        row = self._job_from_form()
        if not row:
            return
        self.jobs.append(row)
        self.job_list.insert("end", str(row["job"]))
        self._refresh_job_choices()

    def _update_job(self) -> None:
        sel = self.job_list.curselection()
        if not sel:
            return
        row = self._job_from_form()
        if not row:
            return
        idx = sel[0]
        self.jobs[idx] = row
        self.job_list.delete(idx)
        self.job_list.insert(idx, str(row["job"]))
        self._refresh_job_choices()

    def _delete_job(self) -> None:
        sel = self.job_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.job_list.delete(idx)
        self.jobs.pop(idx)
        self._refresh_job_choices()

    def _save_jobs(self) -> None:
        save_job_defs(self.jobs)
        self._refresh_job_choices()
        messagebox.showinfo("저장 완료", "직업 데이터를 저장했습니다.")

    # ---------- Action tab ----------
    def _build_action_tab(self) -> None:
        left = ttk.Frame(self.action_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.action_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.action_list = tk.Listbox(left, width=28, height=25, exportselection=False)
        self.action_list.pack(fill="y")
        self.action_list.bind("<<ListboxSelect>>", self._on_action_select)
        for row in self.actions:
            self.action_list.insert("end", str(row.get("name", "")))

        ttk.Label(right, text="행동명").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(right, text="소요 시간(분, 10분 단위)").grid(row=1, column=0, sticky="w", pady=2)
        self.action_name = ttk.Entry(right, width=43)
        self.action_duration = ttk.Entry(right, width=43)
        self.action_name.grid(row=0, column=1, sticky="w", pady=2)
        self.action_duration.grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(right, text="도구는 자동으로 [\"도구\"] 로 저장됩니다.").grid(row=2, column=1, sticky="w", pady=2)

        btns = ttk.Frame(right)
        btns.grid(row=3, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btns, text="추가", command=self._add_action).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_action).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_action).pack(side="left", padx=3)

    def _on_action_select(self, _=None) -> None:
        sel = self.action_list.curselection()
        if not sel:
            return
        row = self.actions[sel[0]]
        self.action_name.delete(0, "end")
        self.action_name.insert(0, str(row.get("name", "")))
        self.action_duration.delete(0, "end")
        self.action_duration.insert(0, str(row.get("duration_minutes", int(row.get("duration_hours", 1)) * 60)))

    def _action_from_form(self) -> dict[str, object] | None:
        try:
            name = self.action_name.get().strip()
            if not name:
                return None
            return {
                "name": name,
                "duration_minutes": max(10, (int(self.action_duration.get().strip() or "10") // 10) * 10),
                "required_tools": ["도구"],
            }
        except Exception:
            messagebox.showwarning("경고", "행동 입력값(JSON/숫자)을 확인하세요.")
            return None

    def _add_action(self) -> None:
        row = self._action_from_form()
        if not row:
            return
        self.actions.append(row)
        self.action_list.insert("end", str(row["name"]))

    def _update_action(self) -> None:
        sel = self.action_list.curselection()
        if not sel:
            return
        row = self._action_from_form()
        if not row:
            return
        idx = sel[0]
        self.actions[idx] = row
        self.action_list.delete(idx)
        self.action_list.insert(idx, str(row["name"]))

    def _delete_action(self) -> None:
        sel = self.action_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.action_list.delete(idx)
        self.actions.pop(idx)


    # ---------- Sim tab ----------
    def _build_sim_tab(self) -> None:
        frame = ttk.Frame(self.sim_tab)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        labels = {
            "npc_speed": "NPC 이동속도(px/s)",
            "hunger_gain_per_tick": "틱당 배고픔 증가",
            "fatigue_gain_per_tick": "틱당 피로 증가",
            "meal_hunger_restore": "식사 시 배고픔 회복",
            "rest_fatigue_restore": "휴식 시 피로 회복",
            "potion_heal": "포션 회복량",
            "explore_duration_ticks": "탐색 지속 틱(6/12/18)",
        }

        self.sim_entries: dict[str, ttk.Entry] = {}
        for i, (key, label) in enumerate(labels.items()):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=4)
            entry = ttk.Entry(frame, width=24)
            entry.grid(row=i, column=1, sticky="w", pady=4)
            entry.insert(0, str(self.sim.get(key, 0.0)))
            self.sim_entries[key] = entry

        ttk.Button(frame, text="저장", command=self._save_sim).grid(row=len(labels), column=0, sticky="w", pady=12)

    def _save_sim(self) -> None:
        out: dict[str, float] = {}
        try:
            for key, widget in self.sim_entries.items():
                if key == "explore_duration_ticks":
                    val = int(float(widget.get().strip()))
                    if val not in (6, 12, 18):
                        messagebox.showwarning("경고", "탐색 지속 틱은 6, 12, 18 중 하나여야 합니다.")
                        return
                    out[key] = float(val)
                else:
                    out[key] = float(widget.get().strip())
        except ValueError:
            messagebox.showwarning("경고", "시뮬레이션 설정은 숫자로 입력하세요.")
            return
        save_sim_settings(out)
        messagebox.showinfo("저장 완료", "시뮬레이션 설정을 저장했습니다.")

    # ---------- Combat tab ----------
    def _build_combat_tab(self) -> None:
        frame = ttk.Frame(self.combat_tab)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        self.combat_entries: dict[str, ttk.Entry] = {}
        labels = {
            "hostile_race": "적대 종족명",
            "engage_range_tiles": "전투 시작 거리(타일)",
            "base_hit_chance": "기본 명중률",
            "agility_evasion_scale": "민첩 회피 계수",
            "min_damage": "최소 피해",
            "max_damage": "최대 피해",
            "strength_damage_scale": "힘 피해 계수",
            "adventurer_attack_bonus": "모험가 공격 보너스",
            "hostile_attack_bonus": "적대 공격 보너스",
        }

        for idx, (key, label) in enumerate(labels.items()):
            ttk.Label(frame, text=label).grid(row=idx, column=0, sticky="w", pady=4)
            entry = ttk.Entry(frame, width=24)
            entry.grid(row=idx, column=1, sticky="w", pady=4)
            entry.insert(0, str(self.combat.get(key, "")))
            self.combat_entries[key] = entry

        ttk.Button(frame, text="저장", command=self._save_combat).grid(row=len(labels), column=0, sticky="w", pady=12)

    def _save_combat(self) -> None:
        try:
            out = {
                "hostile_race": self.combat_entries["hostile_race"].get().strip() or "적대",
                "engage_range_tiles": int(self.combat_entries["engage_range_tiles"].get().strip() or "2"),
                "base_hit_chance": float(self.combat_entries["base_hit_chance"].get().strip() or "0.75"),
                "agility_evasion_scale": float(self.combat_entries["agility_evasion_scale"].get().strip() or "0.015"),
                "min_damage": int(self.combat_entries["min_damage"].get().strip() or "5"),
                "max_damage": int(self.combat_entries["max_damage"].get().strip() or "14"),
                "strength_damage_scale": float(self.combat_entries["strength_damage_scale"].get().strip() or "0.45"),
                "adventurer_attack_bonus": float(self.combat_entries["adventurer_attack_bonus"].get().strip() or "0.1"),
                "hostile_attack_bonus": float(self.combat_entries["hostile_attack_bonus"].get().strip() or "0.05"),
            }
        except ValueError:
            messagebox.showwarning("경고", "전투 설정 수치를 확인하세요.")
            return

        COMBAT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("저장 완료", "전투 설정을 저장했습니다.")


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
