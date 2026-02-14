#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from editable_data import (
    VALID_GENDERS,
    load_entities,
    load_item_defs,
    load_job_defs,
    load_job_names,
    load_monster_templates,
    load_npc_templates,
    load_races,
    load_sim_settings,
    save_entities,
    save_item_defs,
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
        self.entities = load_entities()
        self.jobs = load_job_defs()
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
        self.entity_tab = ttk.Frame(notebook)
        self.job_tab = ttk.Frame(notebook)
        self.sim_tab = ttk.Frame(notebook)
        self.combat_tab = ttk.Frame(notebook)

        notebook.add(self.item_tab, text="아이템")
        notebook.add(self.npc_tab, text="NPC")
        notebook.add(self.monster_tab, text="몬스터")
        notebook.add(self.race_tab, text="종족")
        notebook.add(self.entity_tab, text="엔티티")
        notebook.add(self.job_tab, text="직업")
        notebook.add(self.sim_tab, text="시뮬 설정")
        notebook.add(self.combat_tab, text="전투")

        self._build_item_tab()
        self._build_person_tab(self.npc_tab, mode="npc")
        self._build_person_tab(self.monster_tab, mode="monster")
        self._build_race_tab()
        self._build_entity_tab()
        self._build_job_tab()
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

        self.item_list = tk.Listbox(left, width=34, height=30)
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

        self.item_is_craftable = tk.BooleanVar(value=False)
        self.item_is_gatherable = tk.BooleanVar(value=False)
        ttk.Checkbutton(right, text="제작 가능", variable=self.item_is_craftable).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(right, text="채집 가능", variable=self.item_is_gatherable).grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(right, text="제작 재료(JSON)").grid(row=3, column=0, sticky="nw", pady=2)
        self.item_craft_inputs = tk.Text(right, width=40, height=4)
        self.item_craft_inputs.grid(row=3, column=1, sticky="w", pady=2)

        self.item_numbers: dict[str, ttk.Entry] = {}
        numeric_fields = [
            ("craft_time", "제작 시간"),
            ("craft_fatigue", "제작 피로"),
            ("craft_amount", "제작 수량"),
            ("gather_time", "채집 시간"),
            ("gather_amount", "채집 수량"),
            ("gather_fatigue", "채집 피로"),
        ]
        row_idx = 4
        for key, label in numeric_fields:
            ttk.Label(right, text=label).grid(row=row_idx, column=0, sticky="w", pady=2)
            entry = ttk.Entry(right, width=44)
            entry.grid(row=row_idx, column=1, sticky="w", pady=2)
            self.item_numbers[key] = entry
            row_idx += 1

        ttk.Label(right, text="제작 설비").grid(row=row_idx, column=0, sticky="w", pady=2)
        self.item_craft_station = ttk.Entry(right, width=44)
        self.item_craft_station.grid(row=row_idx, column=1, sticky="w", pady=2)
        row_idx += 1

        ttk.Label(right, text="채집 장소").grid(row=row_idx, column=0, sticky="w", pady=2)
        self.item_gather_spot = ttk.Entry(right, width=44)
        self.item_gather_spot.grid(row=row_idx, column=1, sticky="w", pady=2)

        btns = ttk.Frame(right)
        btns.grid(row=row_idx + 1, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btns, text="추가", command=self._add_item).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_item).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_item).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=self._save_items).pack(side="left", padx=3)

    def _item_from_form(self) -> dict[str, object] | None:
        try:
            return {
                "key": self.item_key.get().strip(),
                "display": self.item_display.get().strip(),
                "is_craftable": bool(self.item_is_craftable.get()),
                "is_gatherable": bool(self.item_is_gatherable.get()),
                "craft_inputs": json.loads(self.item_craft_inputs.get("1.0", "end").strip() or "{}"),
                "craft_time": int(self.item_numbers["craft_time"].get().strip() or "0"),
                "craft_fatigue": int(self.item_numbers["craft_fatigue"].get().strip() or "0"),
                "craft_station": self.item_craft_station.get().strip(),
                "craft_amount": int(self.item_numbers["craft_amount"].get().strip() or "0"),
                "gather_time": int(self.item_numbers["gather_time"].get().strip() or "0"),
                "gather_amount": int(self.item_numbers["gather_amount"].get().strip() or "0"),
                "gather_fatigue": int(self.item_numbers["gather_fatigue"].get().strip() or "0"),
                "gather_spot": self.item_gather_spot.get().strip(),
            }
        except Exception:
            messagebox.showwarning("경고", "아이템 입력값(JSON/숫자)을 확인하세요.")
            return None

    def _on_item_select(self, _=None) -> None:
        sel = self.item_list.curselection()
        if not sel:
            return
        row = self.items[sel[0]]
        self.item_key.delete(0, "end")
        self.item_key.insert(0, str(row.get("key", "")))
        self.item_display.delete(0, "end")
        self.item_display.insert(0, str(row.get("display", "")))
        self.item_is_craftable.set(bool(row.get("is_craftable", False)))
        self.item_is_gatherable.set(bool(row.get("is_gatherable", False)))
        self.item_craft_inputs.delete("1.0", "end")
        self.item_craft_inputs.insert("1.0", json.dumps(row.get("craft_inputs", {}), ensure_ascii=False, indent=2))
        for key, entry in self.item_numbers.items():
            entry.delete(0, "end")
            entry.insert(0, str(row.get(key, 0)))
        self.item_craft_station.delete(0, "end")
        self.item_craft_station.insert(0, str(row.get("craft_station", "")))
        self.item_gather_spot.delete(0, "end")
        self.item_gather_spot.insert(0, str(row.get("gather_spot", "")))

    def _add_item(self) -> None:
        row = self._item_from_form()
        if not row or not row.get("key") or not row.get("display"):
            messagebox.showwarning("경고", "아이템 키/표시 이름을 입력하세요.")
            return
        self.items.append(row)
        self.item_list.insert("end", f"{row['key']} ({row['display']})")

    def _update_item(self) -> None:
        sel = self.item_list.curselection()
        if not sel:
            return
        row = self._item_from_form()
        if not row or not row.get("key") or not row.get("display"):
            messagebox.showwarning("경고", "아이템 키/표시 이름을 입력하세요.")
            return
        idx = sel[0]
        self.items[idx] = row
        self.item_list.delete(idx)
        self.item_list.insert(idx, f"{row['key']} ({row['display']})")

    def _delete_item(self) -> None:
        sel = self.item_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.item_list.delete(idx)
        self.items.pop(idx)

    def _save_items(self) -> None:
        save_item_defs(self.items)
        messagebox.showinfo("저장 완료", "아이템 데이터를 저장했습니다.")

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
            if not sel:
                messagebox.showwarning("경고", "저장할 NPC/몬스터 행을 먼저 선택하세요.")
                return
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

        self.race_list = tk.Listbox(left, width=30, height=28)
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

    # ---------- Entity tab ----------
    def _build_entity_tab(self) -> None:
        left = ttk.Frame(self.entity_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.entity_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.entity_list = tk.Listbox(left, width=36, height=30)
        self.entity_list.pack(fill="y")
        self.entity_list.bind("<<ListboxSelect>>", self._on_entity_select)
        for row in self.entities:
            self.entity_list.insert("end", f"{row.get('type','')}:{row.get('name','')} ({row.get('x',0)},{row.get('y',0)})")

        labels = ["유형", "이름", "X", "Y", "재고(자원형만)"]
        for idx, label in enumerate(labels):
            ttk.Label(right, text=label).grid(row=idx, column=0, sticky="w", pady=2)

        self.entity_type = ttk.Combobox(right, values=["workbench", "resource"], state="readonly", width=40)
        self.entity_name = ttk.Entry(right, width=43)
        self.entity_x = ttk.Entry(right, width=43)
        self.entity_y = ttk.Entry(right, width=43)
        self.entity_stock = ttk.Entry(right, width=43)

        self.entity_type.grid(row=0, column=1, sticky="w", pady=2)
        self.entity_name.grid(row=1, column=1, sticky="w", pady=2)
        self.entity_x.grid(row=2, column=1, sticky="w", pady=2)
        self.entity_y.grid(row=3, column=1, sticky="w", pady=2)
        self.entity_stock.grid(row=4, column=1, sticky="w", pady=2)

        btns = ttk.Frame(right)
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btns, text="추가", command=self._add_entity).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_entity).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_entity).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=self._save_entities).pack(side="left", padx=3)

    def _entity_from_form(self) -> dict[str, object] | None:
        try:
            out = {
                "type": self.entity_type.get().strip() or "workbench",
                "name": self.entity_name.get().strip(),
                "x": int(self.entity_x.get().strip() or "0"),
                "y": int(self.entity_y.get().strip() or "0"),
            }
            if out["type"] == "resource":
                out["stock"] = max(0, int(self.entity_stock.get().strip() or "0"))
            return out if out["name"] else None
        except ValueError:
            messagebox.showwarning("경고", "좌표/재고는 숫자로 입력하세요.")
            return None

    def _on_entity_select(self, _=None) -> None:
        sel = self.entity_list.curselection()
        if not sel:
            return
        row = self.entities[sel[0]]
        self.entity_type.set(str(row.get("type", "workbench")))
        self.entity_name.delete(0, "end")
        self.entity_name.insert(0, str(row.get("name", "")))
        self.entity_x.delete(0, "end")
        self.entity_x.insert(0, str(row.get("x", 0)))
        self.entity_y.delete(0, "end")
        self.entity_y.insert(0, str(row.get("y", 0)))
        self.entity_stock.delete(0, "end")
        self.entity_stock.insert(0, str(row.get("stock", 0)))

    def _add_entity(self) -> None:
        row = self._entity_from_form()
        if not row:
            return
        self.entities.append(row)
        self.entity_list.insert("end", f"{row['type']}:{row['name']} ({row['x']},{row['y']})")

    def _update_entity(self) -> None:
        sel = self.entity_list.curselection()
        if not sel:
            return
        row = self._entity_from_form()
        if not row:
            return
        idx = sel[0]
        self.entities[idx] = row
        self.entity_list.delete(idx)
        self.entity_list.insert(idx, f"{row['type']}:{row['name']} ({row['x']},{row['y']})")

    def _delete_entity(self) -> None:
        sel = self.entity_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.entity_list.delete(idx)
        self.entities.pop(idx)

    def _save_entities(self) -> None:
        save_entities(self.entities)
        messagebox.showinfo("저장 완료", "엔티티 데이터를 저장했습니다.")

    # ---------- Job tab ----------
    def _build_job_tab(self) -> None:
        left = ttk.Frame(self.job_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.job_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.job_list = tk.Listbox(left, width=28, height=25)
        self.job_list.pack(fill="y")
        self.job_list.bind("<<ListboxSelect>>", self._on_job_select)
        for row in self.jobs:
            self.job_list.insert("end", str(row.get("job", "")))

        ttk.Label(right, text="직업").grid(row=0, column=0, sticky="w", pady=2)
        self.job_name = ttk.Combobox(right, values=self.job_names, state="readonly", width=40)
        self.job_name.grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(right, text="생산(JSON)").grid(row=1, column=0, sticky="nw", pady=2)
        ttk.Label(right, text="소모(JSON)").grid(row=2, column=0, sticky="nw", pady=2)
        ttk.Label(right, text="가공(JSON)").grid(row=3, column=0, sticky="nw", pady=2)
        self.job_primary_output = tk.Text(right, width=40, height=3)
        self.job_input_need = tk.Text(right, width=40, height=3)
        self.job_craft_output = tk.Text(right, width=40, height=3)
        self.job_primary_output.grid(row=1, column=1, sticky="w", pady=2)
        self.job_input_need.grid(row=2, column=1, sticky="w", pady=2)
        self.job_craft_output.grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(right, text="판매 아이템(쉼표)").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Label(right, text="판매 한도").grid(row=5, column=0, sticky="w", pady=2)
        self.job_sell_items = ttk.Entry(right, width=43)
        self.job_sell_limit = ttk.Entry(right, width=43)
        self.job_sell_items.grid(row=4, column=1, sticky="w", pady=2)
        self.job_sell_limit.grid(row=5, column=1, sticky="w", pady=2)

        btns = ttk.Frame(right)
        btns.grid(row=6, column=0, columnspan=2, sticky="w", pady=10)
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
        self.job_primary_output.delete("1.0", "end")
        self.job_primary_output.insert("1.0", json.dumps(row.get("primary_output", {}), ensure_ascii=False, indent=2))
        self.job_input_need.delete("1.0", "end")
        self.job_input_need.insert("1.0", json.dumps(row.get("input_need", {}), ensure_ascii=False, indent=2))
        self.job_craft_output.delete("1.0", "end")
        self.job_craft_output.insert("1.0", json.dumps(row.get("craft_output", {}), ensure_ascii=False, indent=2))
        self.job_sell_items.delete(0, "end")
        self.job_sell_items.insert(0, ",".join([str(x) for x in row.get("sell_items", [])]))
        self.job_sell_limit.delete(0, "end")
        self.job_sell_limit.insert(0, str(row.get("sell_limit", 3)))

    def _job_from_form(self) -> dict[str, object] | None:
        try:
            name = self.job_name.get().strip()
            if not name:
                return None
            return {
                "job": name,
                "primary_output": json.loads(self.job_primary_output.get("1.0", "end").strip() or "{}"),
                "input_need": json.loads(self.job_input_need.get("1.0", "end").strip() or "{}"),
                "craft_output": json.loads(self.job_craft_output.get("1.0", "end").strip() or "{}"),
                "sell_items": [x.strip() for x in self.job_sell_items.get().split(",") if x.strip()],
                "sell_limit": int(self.job_sell_limit.get().strip() or "3"),
            }
        except Exception:
            messagebox.showwarning("경고", "직업 입력값(JSON/숫자)을 확인하세요.")
            return None

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

    # ---------- Sim tab ----------
    def _build_sim_tab(self) -> None:
        frame = ttk.Frame(self.sim_tab)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        labels = {
            "npc_speed": "NPC 이동속도(px/s)",
            "hunger_gain_per_hour": "시간당 배고픔 증가",
            "fatigue_gain_per_hour": "시간당 피로 증가",
            "meal_hunger_restore": "식사 시 배고픔 회복",
            "rest_fatigue_restore": "휴식 시 피로 회복",
            "potion_heal": "포션 회복량",
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
