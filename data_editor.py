#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

from editable_data import (
    VALID_GENDERS,
    VALID_JOBS,
    load_entities,
    load_item_defs,
    load_job_defs,
    load_monster_templates,
    load_npc_templates,
    load_races,
    load_sim_settings,
    save_entities,
    save_item_defs,
    save_job_defs,
    save_monster_templates,
    save_npc_templates,
    save_races,
    save_sim_settings,
)


class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("판타지 마을 데이터 편집기")
        self.geometry("1180x760")

        self.items = load_item_defs()
        self.npcs = load_npc_templates()
        self.monsters = load_monster_templates()
        self.races = load_races()
        self.entities = load_entities()
        self.jobs = load_job_defs()
        self.sim = load_sim_settings()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.item_tab = ttk.Frame(nb)
        self.npc_tab = ttk.Frame(nb)
        self.monster_tab = ttk.Frame(nb)
        self.race_tab = ttk.Frame(nb)
        self.entity_tab = ttk.Frame(nb)
        self.job_tab = ttk.Frame(nb)
        self.sim_tab = ttk.Frame(nb)

        nb.add(self.item_tab, text="아이템")
        nb.add(self.npc_tab, text="NPC")
        nb.add(self.monster_tab, text="몬스터")
        nb.add(self.race_tab, text="종족")
        nb.add(self.entity_tab, text="엔티티")
        nb.add(self.job_tab, text="직업")
        nb.add(self.sim_tab, text="시뮬레이션 설정")

        self._build_item_tab()
        self._build_people_tab(self.npc_tab, "npc")
        self._build_people_tab(self.monster_tab, "monster")
        self._build_race_tab()
        self._build_entity_tab()
        self._build_job_tab()
        self._build_sim_tab()

    def _race_names(self):
        return [str(r.get("name", "")) for r in self.races]

    def _build_item_tab(self):
        left = ttk.Frame(self.item_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.item_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.item_list = tk.Listbox(left, width=34, height=28)
        self.item_list.pack(fill="y")
        self.item_list.bind("<<ListboxSelect>>", self._on_item_select)
        for it in self.items:
            self.item_list.insert("end", f"{it['key']} ({it['display']})")

        self.item_entries = {}
        row = 0
        for field, label in (("key", "아이템 키"), ("display", "표시 이름"), ("craft_station", "필요 제작대"), ("gather_spot", "채집 장소")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w")
            e = ttk.Entry(right, width=42)
            e.grid(row=row, column=1, sticky="w", pady=2)
            self.item_entries[field] = e
            row += 1

        self.item_vars = {
            "is_craftable": tk.BooleanVar(value=False),
            "is_gatherable": tk.BooleanVar(value=False),
        }
        ttk.Checkbutton(right, text="조합 제작 가능", variable=self.item_vars["is_craftable"]).grid(row=row, column=0, sticky="w")
        ttk.Checkbutton(right, text="채집 생산 가능", variable=self.item_vars["is_gatherable"]).grid(row=row, column=1, sticky="w")
        row += 1

        for field, label in (("craft_time", "조합 시간(틱)"), ("craft_fatigue", "조합 필요 피로"), ("craft_amount", "조합 산출 수량"), ("gather_time", "채집 시간(틱)"), ("gather_amount", "회당 채집량"), ("gather_fatigue", "채집 필요 피로")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w")
            e = ttk.Entry(right, width=20)
            e.grid(row=row, column=1, sticky="w", pady=2)
            self.item_entries[field] = e
            row += 1

        ttk.Label(right, text="조합 재료(JSON)").grid(row=row, column=0, sticky="nw")
        self.item_craft_inputs = tk.Text(right, width=48, height=4)
        self.item_craft_inputs.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        btns = ttk.Frame(right)
        btns.grid(row=row, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="추가", command=self._add_item).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_item).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_item).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(self.items, save_item_defs, "아이템")).pack(side="left", padx=3)

    def _item_from_form(self):
        try:
            return {
                "key": self.item_entries["key"].get().strip(),
                "display": self.item_entries["display"].get().strip(),
                "is_craftable": bool(self.item_vars["is_craftable"].get()),
                "is_gatherable": bool(self.item_vars["is_gatherable"].get()),
                "craft_inputs": json.loads(self.item_craft_inputs.get("1.0", "end").strip() or "{}"),
                "craft_time": int(self.item_entries["craft_time"].get().strip() or "0"),
                "craft_fatigue": int(self.item_entries["craft_fatigue"].get().strip() or "0"),
                "craft_station": self.item_entries["craft_station"].get().strip(),
                "craft_amount": int(self.item_entries["craft_amount"].get().strip() or "0"),
                "gather_time": int(self.item_entries["gather_time"].get().strip() or "0"),
                "gather_amount": int(self.item_entries["gather_amount"].get().strip() or "0"),
                "gather_fatigue": int(self.item_entries["gather_fatigue"].get().strip() or "0"),
                "gather_spot": self.item_entries["gather_spot"].get().strip(),
            }
        except Exception:
            messagebox.showwarning("경고", "아이템 입력값(JSON/숫자)을 확인하세요.")
            return None

    def _on_item_select(self, _=None):
        sel = self.item_list.curselection()
        if not sel:
            return
        it = self.items[sel[0]]
        for f, e in self.item_entries.items():
            e.delete(0, "end")
            e.insert(0, str(it.get(f, "")))
        self.item_vars["is_craftable"].set(bool(it.get("is_craftable", False)))
        self.item_vars["is_gatherable"].set(bool(it.get("is_gatherable", False)))
        self.item_craft_inputs.delete("1.0", "end")
        self.item_craft_inputs.insert("1.0", json.dumps(it.get("craft_inputs", {}), ensure_ascii=False))

    def _add_item(self):
        row = self._item_from_form()
        if not row or not row["key"] or not row["display"]:
            return
        self.items.append(row)
        self.item_list.insert("end", f"{row['key']} ({row['display']})")

    def _update_item(self):
        sel = self.item_list.curselection()
        if not sel:
            return
        row = self._item_from_form()
        if not row or not row["key"]:
            return
        i = sel[0]
        self.items[i] = row
        self.item_list.delete(i)
        self.item_list.insert(i, f"{row['key']} ({row['display']})")

    def _delete_item(self):
        sel = self.item_list.curselection()
        if not sel:
            return
        i = sel[0]
        self.item_list.delete(i)
        self.items.pop(i)

    def _build_people_tab(self, tab: ttk.Frame, mode: str):
        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        data = self.npcs if mode == "npc" else self.monsters
        lb = tk.Listbox(left, width=28, height=26)
        lb.pack(fill="y")
        for n in data:
            lb.insert("end", f"{n['name']} ({n['race']}/{n['job']})")
        key = f"{mode}_list"
        setattr(self, key, lb)

        entries = {}
        ttk.Label(right, text="이름").grid(row=0, column=0, sticky="w")
        e_name = ttk.Entry(right, width=42)
        e_name.grid(row=0, column=1, sticky="w")
        entries["name"] = e_name

        ttk.Label(right, text="종족").grid(row=1, column=0, sticky="w")
        cb_race = ttk.Combobox(right, values=self._race_names(), state="readonly", width=39)
        cb_race.grid(row=1, column=1, sticky="w")
        entries["race"] = cb_race

        ttk.Label(right, text="성별").grid(row=2, column=0, sticky="w")
        cb_gender = ttk.Combobox(right, values=VALID_GENDERS, state="readonly", width=39)
        cb_gender.grid(row=2, column=1, sticky="w")
        entries["gender"] = cb_gender

        ttk.Label(right, text="나이").grid(row=3, column=0, sticky="w")
        e_age = ttk.Entry(right, width=42)
        e_age.grid(row=3, column=1, sticky="w")
        entries["age"] = e_age

        ttk.Label(right, text="직업").grid(row=4, column=0, sticky="w")
        cb_job = ttk.Combobox(right, values=VALID_JOBS, state="readonly", width=39)
        cb_job.grid(row=4, column=1, sticky="w")
        entries["job"] = cb_job

        # ttk.Label(right, text="키").grid(row=5, column=0, sticky="w")
        # ttk.Label(right, text="몸무게").grid(row=6, column=0, sticky="w")
        # ttk.Label(right, text="목표").grid(row=7, column=0, sticky="w")

        setattr(self, f"{mode}_entries", entries)

        def on_select(_=None):
            sel = lb.curselection()
            if not sel:
                return
            row = data[sel[0]]
            for k, w in entries.items():
                w.delete(0, "end")
                w.insert(0, str(row.get(k, "")))

        lb.bind("<<ListboxSelect>>", on_select)

        def from_form():
            try:
                return {
                    "name": entries["name"].get().strip(),
                    "race": entries["race"].get().strip() or "인간",
                    "gender": entries["gender"].get().strip() or "기타",
                    "age": int(entries["age"].get().strip() or "20"),
                    "job": entries["job"].get().strip() or "농부",
                }
            except Exception:
                messagebox.showwarning("경고", "나이는 숫자로 입력하세요.")
                return None

        def add_row():
            row = from_form()
            if not row or not row["name"]:
                return
            data.append(row)
            lb.insert("end", f"{row['name']} ({row['race']}/{row['job']})")

        def upd_row():
            sel = lb.curselection()
            if not sel:
                return
            row = from_form()
            if not row or not row["name"]:
                return
            i = sel[0]
            data[i] = row
            lb.delete(i)
            lb.insert(i, f"{row['name']} ({row['race']}/{row['job']})")

        def del_row():
            sel = lb.curselection()
            if not sel:
                return
            i = sel[0]
            lb.delete(i)
            data.pop(i)

        save_fn = save_npc_templates if mode == "npc" else save_monster_templates
        btns = ttk.Frame(right)
        btns.grid(row=8, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="추가", command=add_row).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=upd_row).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=del_row).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(data, save_fn, "NPC" if mode == "npc" else "몬스터")).pack(side="left", padx=3)

    def _build_race_tab(self):
        left = ttk.Frame(self.race_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.race_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.race_list = tk.Listbox(left, width=26, height=25)
        self.race_list.pack(fill="y")
        for r in self.races:
            hostile = "*" if r.get("is_hostile") else ""
            self.race_list.insert("end", f"{r['name']}{hostile}")

        self.race_entries = {}
        for i, (k, lab) in enumerate((("name", "종족명"), ("str_bonus", "힘 보너스"), ("agi_bonus", "민첩 보너스"), ("hp_bonus", "최대체력 보너스"), ("speed_bonus", "이동속도 보너스"))):
            ttk.Label(right, text=lab).grid(row=i, column=0, sticky="w")
            e = ttk.Entry(right, width=36)
            e.grid(row=i, column=1, sticky="w", pady=2)
            self.race_entries[k] = e
        self.race_hostile = tk.BooleanVar(value=False)
        ttk.Checkbutton(right, text="적대(몬스터 취급)", variable=self.race_hostile).grid(row=5, column=0, columnspan=2, sticky="w")

        def on_select(_=None):
            sel = self.race_list.curselection()
            if not sel:
                return
            row = self.races[sel[0]]
            for k, e in self.race_entries.items():
                e.delete(0, "end")
                e.insert(0, str(row.get(k, "")))
            self.race_hostile.set(bool(row.get("is_hostile", False)))

        self.race_list.bind("<<ListboxSelect>>", on_select)

        def from_form():
            try:
                return {
                    "name": self.race_entries["name"].get().strip(),
                    "is_hostile": bool(self.race_hostile.get()),
                    "str_bonus": int(self.race_entries["str_bonus"].get().strip() or "0"),
                    "agi_bonus": int(self.race_entries["agi_bonus"].get().strip() or "0"),
                    "hp_bonus": int(self.race_entries["hp_bonus"].get().strip() or "0"),
                    "speed_bonus": float(self.race_entries["speed_bonus"].get().strip() or "0"),
                }
            except Exception:
                messagebox.showwarning("경고", "종족 보너스는 숫자여야 합니다.")
                return None

        def add_row():
            row = from_form()
            if not row or not row["name"]:
                return
            self.races.append(row)
            self.race_list.insert("end", f"{row['name']}{'*' if row['is_hostile'] else ''}")

        def upd_row():
            sel = self.race_list.curselection()
            if not sel:
                return
            row = from_form()
            if not row or not row["name"]:
                return
            i = sel[0]
            self.races[i] = row
            self.race_list.delete(i)
            self.race_list.insert(i, f"{row['name']}{'*' if row['is_hostile'] else ''}")

        def del_row():
            sel = self.race_list.curselection()
            if not sel:
                return
            i = sel[0]
            self.race_list.delete(i)
            self.races.pop(i)

        btns = ttk.Frame(right)
        btns.grid(row=6, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="추가", command=add_row).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=upd_row).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=del_row).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(self.races, save_races, "종족")).pack(side="left", padx=3)

    def _build_entity_tab(self):
        left = ttk.Frame(self.entity_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.entity_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.entity_list = tk.Listbox(left, width=36, height=25)
        self.entity_list.pack(fill="y")
        for e in self.entities:
            self.entity_list.insert("end", f"{e.get('type')}:{e.get('name')}@({e.get('x')},{e.get('y')})")

        self.entity_type = ttk.Combobox(right, values=["workbench", "resource"], state="readonly", width=24)
        self.entity_name = ttk.Entry(right, width=30)
        self.entity_x = ttk.Entry(right, width=16)
        self.entity_y = ttk.Entry(right, width=16)
        self.entity_stock = ttk.Entry(right, width=16)
        ttk.Label(right, text="종류(workbench/resource)").grid(row=0, column=0, sticky="w")
        self.entity_type.grid(row=0, column=1, sticky="w")
        ttk.Label(right, text="이름").grid(row=1, column=0, sticky="w")
        self.entity_name.grid(row=1, column=1, sticky="w")
        ttk.Label(right, text="x").grid(row=2, column=0, sticky="w")
        self.entity_x.grid(row=2, column=1, sticky="w")
        ttk.Label(right, text="y").grid(row=3, column=0, sticky="w")
        self.entity_y.grid(row=3, column=1, sticky="w")
        ttk.Label(right, text="재고(resource 전용)").grid(row=4, column=0, sticky="w")
        self.entity_stock.grid(row=4, column=1, sticky="w")

        def on_select(_=None):
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

        self.entity_list.bind("<<ListboxSelect>>", on_select)

        def from_form():
            try:
                row = {
                    "type": self.entity_type.get().strip() or "workbench",
                    "name": self.entity_name.get().strip(),
                    "x": int(self.entity_x.get().strip() or "0"),
                    "y": int(self.entity_y.get().strip() or "0"),
                }
                if row["type"] == "resource":
                    row["stock"] = int(self.entity_stock.get().strip() or "0")
                return row
            except Exception:
                messagebox.showwarning("경고", "엔티티 좌표/재고는 숫자여야 합니다.")
                return None

        def add_row():
            row = from_form()
            if not row or not row["name"]:
                return
            self.entities.append(row)
            self.entity_list.insert("end", f"{row.get('type')}:{row.get('name')}@({row.get('x')},{row.get('y')})")

        def upd_row():
            sel = self.entity_list.curselection()
            if not sel:
                return
            row = from_form()
            if not row or not row["name"]:
                return
            i = sel[0]
            self.entities[i] = row
            self.entity_list.delete(i)
            self.entity_list.insert(i, f"{row.get('type')}:{row.get('name')}@({row.get('x')},{row.get('y')})")

        def del_row():
            sel = self.entity_list.curselection()
            if not sel:
                return
            i = sel[0]
            self.entity_list.delete(i)
            self.entities.pop(i)

        btns = ttk.Frame(right)
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="추가", command=add_row).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=upd_row).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=del_row).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(self.entities, save_entities, "엔티티")).pack(side="left", padx=3)

    def _build_job_tab(self):
        # 기존 기능 유지
        frame = ttk.Frame(self.job_tab)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        self.job_text = tk.Text(frame, width=110, height=30)
        self.job_text.pack()
        self.job_text.insert("1.0", json.dumps(self.jobs, ensure_ascii=False, indent=2))
        ttk.Button(frame, text="저장", command=self._save_jobs).pack(anchor="w", pady=6)

    def _save_jobs(self):
        try:
            self.jobs = json.loads(self.job_text.get("1.0", "end").strip() or "[]")
        except Exception:
            messagebox.showwarning("경고", "직업 JSON 형식을 확인하세요.")
            return
        self._save_list(self.jobs, save_job_defs, "직업")

    def _build_sim_tab(self):
        frame = ttk.Frame(self.sim_tab)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        self.sim_entries = {}
        labels = {
            "npc_speed": "NPC 이동속도(px/s)",
            "hunger_gain_per_hour": "시간당 배고픔 증가",
            "fatigue_gain_per_hour": "시간당 피로 증가",
            "meal_hunger_restore": "식사 시 배고픔 회복",
            "rest_fatigue_restore": "휴식 시 피로 회복",
            "potion_heal": "포션 회복량",
        }
        for i, (k, lab) in enumerate(labels.items()):
            ttk.Label(frame, text=lab).grid(row=i, column=0, sticky="w", pady=3)
            e = ttk.Entry(frame, width=22)
            e.grid(row=i, column=1, sticky="w", pady=3)
            e.insert(0, str(self.sim.get(k, 0)))
            self.sim_entries[k] = e
        ttk.Button(frame, text="저장", command=self._save_sim).grid(row=len(labels), column=0, sticky="w", pady=8)

    def _save_sim(self):
        out = {}
        try:
            for k, e in self.sim_entries.items():
                out[k] = float(e.get().strip())
        except Exception:
            messagebox.showwarning("경고", "시뮬레이션 값은 숫자만 가능합니다.")
            return
        self._save_list(out, save_sim_settings, "시뮬레이션 설정")

    def _save_list(self, obj, fn, label: str):
        fn(obj)
        messagebox.showinfo("저장 완료", f"{label} 데이터를 저장했습니다.")


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
