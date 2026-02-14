#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

from editable_data import (
    VALID_GENDERS,
    VALID_JOBS,
    load_all_data,
    save_entities,
    save_item_defs,
    save_job_defs,
    save_monster_templates,
    save_npc_templates,
    save_sim_settings,
)


class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("판타지 마을 데이터 편집기")
        self.geometry("1100x760")

        data = load_all_data()
        self.items = data["items"]
        self.npcs = data["npcs"]
        self.monsters = data["monsters"]
        self.races = data["races"]
        self.entities = data["entities"]
        self.jobs = data["jobs"]
        self.sim = data["sim"]

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.item_tab = ttk.Frame(nb)
        self.npc_tab = ttk.Frame(nb)
        self.monster_tab = ttk.Frame(nb)
        self.entity_tab = ttk.Frame(nb)
        self.job_tab = ttk.Frame(nb)
        self.sim_tab = ttk.Frame(nb)

        nb.add(self.item_tab, text="아이템")
        nb.add(self.npc_tab, text="NPC")
        nb.add(self.monster_tab, text="몬스터")
        nb.add(self.entity_tab, text="엔티티")
        nb.add(self.job_tab, text="직업")
        nb.add(self.sim_tab, text="시뮬레이션 설정")

        self._build_item_tab()
        self._build_npc_tab()
        self._build_monster_tab()
        self._build_entity_tab()
        self._build_job_tab()
        self._build_sim_tab()

    def _race_names(self) -> list[str]:
        names = [str(r.get("name", "")).strip() for r in self.races if isinstance(r, dict)]
        names = [n for n in names if n]
        return names or ["인간"]

    def _build_npc_tab(self):
        left = ttk.Frame(self.npc_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.npc_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.npc_list = tk.Listbox(left, width=30, height=28)
        self.npc_list.pack(fill="y")
        self.npc_list.bind("<<ListboxSelect>>", self._on_npc_select)
        for row in self.npcs:
            self.npc_list.insert("end", f"{row['name']} ({row['race']}/{row['job']})")

        self.npc_entries = {}
        labels = [("name", "이름"), ("race", "종족"), ("gender", "성별"), ("age", "나이"), ("job", "직업")]
        for idx, (key, label) in enumerate(labels):
            ttk.Label(right, text=label).grid(row=idx, column=0, sticky="w", pady=2)
            if key == "job":
                widget = ttk.Combobox(right, values=VALID_JOBS, state="readonly", width=39)
            elif key == "gender":
                widget = ttk.Combobox(right, values=VALID_GENDERS, state="readonly", width=39)
            else:
                widget = ttk.Entry(right, width=42)
            widget.grid(row=idx, column=1, sticky="w", pady=2)
            self.npc_entries[key] = widget

        btns = ttk.Frame(right)
        btns.grid(row=len(labels), column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="추가", command=self._add_npc).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_npc).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_npc).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(self.npcs, save_npc_templates, "NPC")).pack(side="left", padx=3)

    def _npc_from_form(self):
        try:
            save_fn(rows)
        except Exception as e:
            messagebox.showerror("저장 실패", f"{label} 저장 중 오류: {e}")
            return
        messagebox.showinfo("저장 완료", f"{label} 데이터를 저장했습니다.")

    def _race_names(self) -> list[str]:
        names = [str(r.get("name", "")).strip() for r in self.races if isinstance(r, dict)]
        return [n for n in names if n] or ["인간"]

    def _build_item_tab(self):
        left = ttk.Frame(self.item_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.item_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.item_list = tk.Listbox(left, width=32, height=30)
        self.item_list.pack(fill="y")
        self.item_list.bind("<<ListboxSelect>>", self._on_item_select)
        for it in self.items:
            self.item_list.insert("end", f"{it.get('key','')} ({it.get('display','')})")

        ttk.Label(right, text="아이템 키").grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="표시 이름").grid(row=1, column=0, sticky="w")
        self.item_key = ttk.Entry(right, width=44)
        self.item_display = ttk.Entry(right, width=44)
        self.item_key.grid(row=0, column=1, sticky="w", pady=4)
        self.item_display.grid(row=1, column=1, sticky="w", pady=4)

        self.item_entries = {"key": self.item_key, "display": self.item_display}
        self.item_vars = {"is_craftable": tk.BooleanVar(value=False), "is_gatherable": tk.BooleanVar(value=False)}
        ttk.Checkbutton(right, text="제작 가능", variable=self.item_vars["is_craftable"]).grid(row=2, column=1, sticky="w")
        ttk.Checkbutton(right, text="채집 가능", variable=self.item_vars["is_gatherable"]).grid(row=3, column=1, sticky="w")
        ttk.Label(right, text="가공 재료(JSON)").grid(row=2, column=0, sticky="nw")
        self.item_craft_inputs = tk.Text(right, width=40, height=3)
        self.item_craft_inputs.grid(row=4, column=1, sticky="w", pady=4)

        btns = ttk.Frame(right)
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="추가", command=self._add_item).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_item).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_item).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(self.items, save_item_defs, "아이템")).pack(side="left", padx=3)

    def _item_from_form(self):
        try:
            return {
                "key": self.item_key.get().strip(),
                "display": self.item_display.get().strip(),
                "is_craftable": bool(self.item_vars["is_craftable"].get()),
                "is_gatherable": bool(self.item_vars["is_gatherable"].get()),
                "craft_inputs": json.loads(self.item_craft_inputs.get("1.0", "end").strip() or "{}"),
                "craft_time": 0,
                "craft_fatigue": 0,
                "craft_station": "",
                "craft_amount": 0,
                "gather_time": 0,
                "gather_amount": 0,
                "gather_fatigue": 0,
                "gather_spot": "",
            }
        except Exception:
            messagebox.showwarning("경고", "아이템 입력값(JSON/숫자)을 확인하세요.")
            return None

    def _on_item_select(self, _=None):
        sel = self.item_list.curselection()
        if not sel:
            return
        row = self.items[sel[0]]
        self.item_key.delete(0, "end")
        self.item_key.insert(0, str(row.get("key", "")))
        self.item_display.delete(0, "end")
        self.item_display.insert(0, str(row.get("display", "")))
        self.item_vars["is_craftable"].set(bool(row.get("is_craftable", False)))
        self.item_vars["is_gatherable"].set(bool(row.get("is_gatherable", False)))
        self.item_craft_inputs.delete("1.0", "end")
        self.item_craft_inputs.insert("1.0", json.dumps(row.get("craft_inputs", {}), ensure_ascii=False))

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
        if not row or not row["key"] or not row["display"]:
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

    def _build_person_tab(self, tab: ttk.Frame, mode: str):
        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        data = self.npcs if mode == "npc" else self.monsters
        lb = tk.Listbox(left, width=34, height=30)
        lb.pack(fill="y")
        for n in data:
            lb.insert("end", f"{n.get('name','')} ({n.get('race','')}/{n.get('job','')})")

        entries = {}
        fields = [("name", "이름"), ("race", "종족"), ("gender", "성별"), ("age", "나이"), ("job", "직업")]
        for i, (f, label) in enumerate(fields):
            ttk.Label(right, text=label).grid(row=i, column=0, sticky="w", pady=2)
            if f == "gender":
                w = ttk.Combobox(right, values=VALID_GENDERS, state="readonly", width=40)
            elif f == "job":
                w = ttk.Combobox(right, values=VALID_JOBS, state="readonly", width=40)
            elif f == "race":
                w = ttk.Combobox(right, values=self._race_names(), state="readonly", width=40)
            else:
                w = ttk.Entry(right, width=43)
            w.grid(row=i, column=1, sticky="w", pady=2)
            entries[f] = w

        def on_select(_=None):
            sel = lb.curselection()
            if not sel:
                return
            row = data[sel[0]]
            entries["name"].delete(0, "end")
            entries["name"].insert(0, str(row.get("name", "")))
            entries["race"].set(str(row.get("race", "인간")))
            entries["gender"].set(str(row.get("gender", "기타")))
            entries["age"].delete(0, "end")
            entries["age"].insert(0, str(row.get("age", 20)))
            entries["job"].set(str(row.get("job", "농부" if mode == "npc" else "모험가")))

        lb.bind("<<ListboxSelect>>", on_select)

        def from_form():
            try:
                return {
                    "name": entries["name"].get().strip(),
                    "race": entries["race"].get().strip() or ("인간" if mode == "npc" else "고블린"),
                    "gender": entries["gender"].get().strip() or "기타",
                    "age": int(entries["age"].get().strip() or "20"),
                    "job": entries["job"].get().strip() or ("농부" if mode == "npc" else "모험가"),
                }
            except ValueError:
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
        btns.grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="추가", command=add_row).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=upd_row).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=del_row).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(data, save_fn, "NPC" if mode == "npc" else "몬스터")).pack(side="left", padx=3)

    def _build_npc_tab(self):
        self._build_person_tab(self.npc_tab, "npc")

    def _build_monster_tab(self):
        self._build_person_tab(self.monster_tab, "monster")

    def _build_entity_tab(self):
        left = ttk.Frame(self.entity_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.entity_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.entity_list = tk.Listbox(left, width=36, height=30)
        self.entity_list.pack(fill="y")
        self.entity_list.bind("<<ListboxSelect>>", self._on_entity_select)
        for e in self.entities:
            self.entity_list.insert("end", f"{e.get('type','')}:{e.get('name','')} ({e.get('x',0)},{e.get('y',0)})")

        ttk.Label(right, text="유형").grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="이름").grid(row=1, column=0, sticky="w")
        ttk.Label(right, text="X").grid(row=2, column=0, sticky="w")
        ttk.Label(right, text="Y").grid(row=3, column=0, sticky="w")
        ttk.Label(right, text="재고(자원형만)").grid(row=4, column=0, sticky="w")

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
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="추가", command=self._add_entity).pack(side="left", padx=3)
        ttk.Button(btns, text="수정", command=self._update_entity).pack(side="left", padx=3)
        ttk.Button(btns, text="삭제", command=self._delete_entity).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(self.entities, save_entities, "엔티티")).pack(side="left", padx=3)

    def _entity_from_form(self):
        try:
            out = {"type": self.entity_type.get().strip() or "workbench", "name": self.entity_name.get().strip(), "x": int(self.entity_x.get().strip() or "0"), "y": int(self.entity_y.get().strip() or "0")}
            if out["type"] == "resource":
                out["stock"] = max(0, int(self.entity_stock.get().strip() or "0"))
            return out if out["name"] else None
        except ValueError:
            messagebox.showwarning("경고", "좌표/재고는 숫자만 입력하세요.")
            return None

    def _on_entity_select(self, _=None):
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

    def _add_entity(self):
        row = self._entity_from_form()
        if not row:
            return
        self.entities.append(row)
        self.entity_list.insert("end", f"{row['type']}:{row['name']} ({row['x']},{row['y']})")

    def _update_entity(self):
        sel = self.entity_list.curselection()
        if not sel:
            return
        row = self._entity_from_form()
        if not row:
            return
        i = sel[0]
        self.entities[i] = row
        self.entity_list.delete(i)
        self.entity_list.insert(i, f"{row['type']}:{row['name']} ({row['x']},{row['y']})")

    def _delete_entity(self):
        sel = self.entity_list.curselection()
        if not sel:
            return
        i = sel[0]
        self.entity_list.delete(i)
        self.entities.pop(i)

    def _build_job_tab(self):
        left = ttk.Frame(self.job_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.job_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.job_list = tk.Listbox(left, width=28, height=25)
        self.job_list.pack(fill="y")
        self.job_list.bind("<<ListboxSelect>>", self._on_job_select)
        for row in self.jobs:
            self.job_list.insert("end", str(row.get("job", "")))

        ttk.Label(right, text="직업").grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="판매 아이템(쉼표)").grid(row=1, column=0, sticky="w")
        ttk.Label(right, text="판매 한도").grid(row=2, column=0, sticky="w")

        self.job_name = ttk.Combobox(right, values=VALID_JOBS, state="readonly", width=40)
        self.job_sell_items = ttk.Entry(right, width=43)
        self.job_sell_limit = ttk.Entry(right, width=43)
        self.job_name.grid(row=0, column=1, sticky="w", pady=2)
        self.job_sell_items.grid(row=1, column=1, sticky="w", pady=2)
        self.job_sell_limit.grid(row=2, column=1, sticky="w", pady=2)

        btns = ttk.Frame(right)
        btns.grid(row=3, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btns, text="추가", command=self._add_job).pack(side="left", padx=4)
        ttk.Button(btns, text="수정", command=self._update_job).pack(side="left", padx=4)
        ttk.Button(btns, text="삭제", command=self._delete_job).pack(side="left", padx=4)
        ttk.Button(btns, text="저장", command=lambda: self._save_list(self.jobs, save_job_defs, "직업")).pack(side="left", padx=4)

    def _on_job_select(self, _ev=None):
        sel = self.job_list.curselection()
        if not sel:
            return
        row = self.jobs[sel[0]]
        self.job_name.set(str(row.get("job", "")))
        self.job_sell_items.delete(0, "end")
        self.job_sell_items.insert(0, ",".join([str(x) for x in row.get("sell_items", [])]))
        self.job_sell_limit.delete(0, "end")
        self.job_sell_limit.insert(0, str(row.get("sell_limit", 3)))

    def _job_from_form(self):
        try:
            job_name = self.job_name.get().strip()
            if not job_name:
                return None
            return {"job": job_name, "primary_output": {}, "input_need": {}, "craft_output": {}, "sell_items": [s.strip() for s in self.job_sell_items.get().split(",") if s.strip()], "sell_limit": int(self.job_sell_limit.get().strip() or "3")}
        except ValueError:
            return None

    def _add_job(self):
        row = self._job_from_form()
        if not row:
            return
        self.jobs.append(row)
        self.job_list.insert("end", str(row["job"]))

    def _update_job(self):
        sel = self.job_list.curselection()
        if not sel:
            return
        row = self._job_from_form()
        if not row:
            return
        i = sel[0]
        self.jobs[i] = row
        self.job_list.delete(i)
        self.job_list.insert(i, str(row["job"]))

    def _delete_job(self):
        sel = self.job_list.curselection()
        if not sel:
            return
        i = sel[0]
        self.job_list.delete(i)
        self.jobs.pop(i)

    def _build_sim_tab(self):
        frame = ttk.Frame(self.sim_tab)
        frame.pack(fill="both", expand=True, padx=16, pady=16)
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
            ttk.Label(frame, text=lab).grid(row=i, column=0, sticky="w", pady=4)
            ent = ttk.Entry(frame, width=24)
            ent.grid(row=i, column=1, sticky="w", pady=4)
            ent.insert(0, str(self.sim.get(k, 0)))
            self.sim_entries[k] = ent

        ttk.Button(frame, text="저장", command=self._save_sim).grid(row=len(labels), column=0, sticky="w", pady=12)

    def _save_sim(self):
        out = {}
        try:
            for k, w in self.sim_entries.items():
                out[k] = float(w.get().strip())
        except ValueError:
            messagebox.showwarning("경고", "시뮬레이션 설정은 숫자로 입력하세요.")
            return
        self._save_list(out, save_sim_settings, "시뮬레이션 설정")


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
