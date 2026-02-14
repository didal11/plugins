#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

from editable_data import (
    VALID_JOBS,
    load_item_defs,
    load_job_defs,
    load_npc_templates,
    load_sim_settings,
    save_item_defs,
    save_job_defs,
    save_npc_templates,
    save_sim_settings,
)


class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("판타지 마을 데이터 편집기")
        self.geometry("980x700")

        self.items = load_item_defs()
        self.npcs = load_npc_templates()
        self.jobs = load_job_defs()
        self.sim = load_sim_settings()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.item_tab = ttk.Frame(nb)
        self.npc_tab = ttk.Frame(nb)
        self.job_tab = ttk.Frame(nb)
        self.sim_tab = ttk.Frame(nb)
        nb.add(self.item_tab, text="아이템")
        nb.add(self.npc_tab, text="NPC")
        nb.add(self.job_tab, text="직업")
        nb.add(self.sim_tab, text="시뮬레이션 설정")

        self._build_item_tab()
        self._build_npc_tab()
        self._build_job_tab()
        self._build_sim_tab()

    def _build_item_tab(self):
        left = ttk.Frame(self.item_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.item_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.item_list = tk.Listbox(left, width=30, height=25)
        self.item_list.pack(fill="y")
        self.item_list.bind("<<ListboxSelect>>", self._on_item_select)

        for it in self.items:
            self.item_list.insert("end", f"{it['key']} ({it['display']})")

        ttk.Label(right, text="아이템 키").grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="표시 이름").grid(row=1, column=0, sticky="w")
        self.item_key = ttk.Entry(right, width=40)
        self.item_disp = ttk.Entry(right, width=40)
        self.item_key.grid(row=0, column=1, sticky="w", pady=4)
        self.item_disp.grid(row=1, column=1, sticky="w", pady=4)

        btns = ttk.Frame(right)
        btns.grid(row=2, column=0, columnspan=2, sticky="w", pady=12)
        ttk.Button(btns, text="추가", command=self._add_item).pack(side="left", padx=4)
        ttk.Button(btns, text="수정", command=self._update_item).pack(side="left", padx=4)
        ttk.Button(btns, text="삭제", command=self._delete_item).pack(side="left", padx=4)
        ttk.Button(btns, text="저장", command=self._save_items).pack(side="left", padx=4)

    def _on_item_select(self, _ev=None):
        sel = self.item_list.curselection()
        if not sel:
            return
        it = self.items[sel[0]]
        self.item_key.delete(0, "end")
        self.item_disp.delete(0, "end")
        self.item_key.insert(0, it["key"])
        self.item_disp.insert(0, it["display"])

    def _add_item(self):
        key = self.item_key.get().strip()
        disp = self.item_disp.get().strip()
        if not key or not disp:
            messagebox.showwarning("경고", "키/표시 이름을 입력하세요.")
            return
        self.items.append({"key": key, "display": disp})
        self.item_list.insert("end", f"{key} ({disp})")

    def _update_item(self):
        sel = self.item_list.curselection()
        if not sel:
            return
        idx = sel[0]
        key = self.item_key.get().strip()
        disp = self.item_disp.get().strip()
        if not key or not disp:
            return
        self.items[idx] = {"key": key, "display": disp}
        self.item_list.delete(idx)
        self.item_list.insert(idx, f"{key} ({disp})")

    def _delete_item(self):
        sel = self.item_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.item_list.delete(idx)
        self.items.pop(idx)

    def _save_items(self):
        save_item_defs(self.items)
        messagebox.showinfo("저장 완료", "아이템 데이터를 저장했습니다.")

    def _build_npc_tab(self):
        left = ttk.Frame(self.npc_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.npc_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.npc_list = tk.Listbox(left, width=30, height=25)
        self.npc_list.pack(fill="y")
        self.npc_list.bind("<<ListboxSelect>>", self._on_npc_select)
        for n in self.npcs:
            self.npc_list.insert("end", f"{n['name']} ({n['job']})")

        fields = ["name", "race", "gender", "age", "height_cm", "weight_kg", "job", "goal"]
        labels = {
            "name": "이름",
            "race": "종족",
            "gender": "성별",
            "age": "나이",
            "height_cm": "키(cm)",
            "weight_kg": "몸무게(kg)",
            "job": "직업",
            "goal": "목표",
        }
        self.npc_entries = {}
        for i, f in enumerate(fields):
            ttk.Label(right, text=labels[f]).grid(row=i, column=0, sticky="w", pady=2)
            w = ttk.Combobox(right, values=VALID_JOBS, state="readonly", width=37) if f == "job" else ttk.Entry(right, width=40)
            w.grid(row=i, column=1, sticky="w", pady=2)
            self.npc_entries[f] = w

        btns = ttk.Frame(right)
        btns.grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=12)
        ttk.Button(btns, text="추가", command=self._add_npc).pack(side="left", padx=4)
        ttk.Button(btns, text="수정", command=self._update_npc).pack(side="left", padx=4)
        ttk.Button(btns, text="삭제", command=self._delete_npc).pack(side="left", padx=4)
        ttk.Button(btns, text="저장", command=self._save_npcs).pack(side="left", padx=4)

    def _on_npc_select(self, _ev=None):
        sel = self.npc_list.curselection()
        if not sel:
            return
        n = self.npcs[sel[0]]
        for k, w in self.npc_entries.items():
            w.delete(0, "end")
            w.insert(0, str(n[k]))

    def _npc_from_form(self):
        try:
            return {
                "name": self.npc_entries["name"].get().strip(),
                "race": self.npc_entries["race"].get().strip() or "인간",
                "gender": self.npc_entries["gender"].get().strip() or "기타",
                "age": int(self.npc_entries["age"].get().strip() or "25"),
                "height_cm": int(self.npc_entries["height_cm"].get().strip() or "170"),
                "weight_kg": int(self.npc_entries["weight_kg"].get().strip() or "65"),
                "job": self.npc_entries["job"].get().strip() or "농부",
                "goal": self.npc_entries["goal"].get().strip() or "돈벌기",
            }
        except ValueError:
            messagebox.showwarning("경고", "나이/키/몸무게는 숫자로 입력하세요.")
            return None

    def _add_npc(self):
        npc = self._npc_from_form()
        if not npc or not npc["name"]:
            return
        self.npcs.append(npc)
        self.npc_list.insert("end", f"{npc['name']} ({npc['job']})")

    def _update_npc(self):
        sel = self.npc_list.curselection()
        if not sel:
            return
        npc = self._npc_from_form()
        if not npc or not npc["name"]:
            return
        idx = sel[0]
        self.npcs[idx] = npc
        self.npc_list.delete(idx)
        self.npc_list.insert(idx, f"{npc['name']} ({npc['job']})")

    def _delete_npc(self):
        sel = self.npc_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.npc_list.delete(idx)
        self.npcs.pop(idx)

    def _save_npcs(self):
        save_npc_templates(self.npcs)
        messagebox.showinfo("저장 완료", "NPC 데이터를 저장했습니다.")

    def _build_job_tab(self):
        left = ttk.Frame(self.job_tab)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(self.job_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.job_list = tk.Listbox(left, width=28, height=20)
        self.job_list.pack(fill="y")
        self.job_list.bind("<<ListboxSelect>>", self._on_job_select)
        for row in self.jobs:
            self.job_list.insert("end", str(row["job"]))

        ttk.Label(right, text="직업").grid(row=0, column=0, sticky="w")
        self.job_name = ttk.Combobox(right, values=VALID_JOBS, state="readonly", width=37)
        self.job_name.grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(right, text="기본 생산(JSON)").grid(row=1, column=0, sticky="nw")
        ttk.Label(right, text="가공 재료(JSON)").grid(row=2, column=0, sticky="nw")
        ttk.Label(right, text="가공 결과(JSON)").grid(row=3, column=0, sticky="nw")
        ttk.Label(right, text="판매 아이템(쉼표)").grid(row=4, column=0, sticky="w")
        ttk.Label(right, text="판매 한도").grid(row=5, column=0, sticky="w")

        self.job_primary = tk.Text(right, width=46, height=4)
        self.job_input = tk.Text(right, width=46, height=4)
        self.job_craft = tk.Text(right, width=46, height=4)
        self.job_sell_items = ttk.Entry(right, width=40)
        self.job_sell_limit = ttk.Entry(right, width=40)

        self.job_primary.grid(row=1, column=1, sticky="w", pady=2)
        self.job_input.grid(row=2, column=1, sticky="w", pady=2)
        self.job_craft.grid(row=3, column=1, sticky="w", pady=2)
        self.job_sell_items.grid(row=4, column=1, sticky="w", pady=2)
        self.job_sell_limit.grid(row=5, column=1, sticky="w", pady=2)

        btns = ttk.Frame(right)
        btns.grid(row=6, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btns, text="추가", command=self._add_job).pack(side="left", padx=4)
        ttk.Button(btns, text="수정", command=self._update_job).pack(side="left", padx=4)
        ttk.Button(btns, text="삭제", command=self._delete_job).pack(side="left", padx=4)
        ttk.Button(btns, text="저장", command=self._save_jobs).pack(side="left", padx=4)

    def _on_job_select(self, _ev=None):
        sel = self.job_list.curselection()
        if not sel:
            return
        row = self.jobs[sel[0]]
        self.job_name.set(str(row.get("job", "")))
        self.job_primary.delete("1.0", "end")
        self.job_input.delete("1.0", "end")
        self.job_craft.delete("1.0", "end")
        self.job_primary.insert("1.0", json.dumps(row.get("primary_output", {}), ensure_ascii=False))
        self.job_input.insert("1.0", json.dumps(row.get("input_need", {}), ensure_ascii=False))
        self.job_craft.insert("1.0", json.dumps(row.get("craft_output", {}), ensure_ascii=False))
        self.job_sell_items.delete(0, "end")
        self.job_sell_items.insert(0, ",".join([str(x) for x in row.get("sell_items", [])]))
        self.job_sell_limit.delete(0, "end")
        self.job_sell_limit.insert(0, str(row.get("sell_limit", 3)))

    def _job_from_form(self):
        try:
            return {
                "job": self.job_name.get().strip(),
                "primary_output": json.loads(self.job_primary.get("1.0", "end").strip() or "{}"),
                "input_need": json.loads(self.job_input.get("1.0", "end").strip() or "{}"),
                "craft_output": json.loads(self.job_craft.get("1.0", "end").strip() or "{}"),
                "sell_items": [s.strip() for s in self.job_sell_items.get().split(",") if s.strip()],
                "sell_limit": int(self.job_sell_limit.get().strip() or "3"),
            }
        except Exception:
            messagebox.showwarning("경고", "직업 데이터 형식(JSON/숫자)을 확인해주세요.")
            return None

    def _add_job(self):
        row = self._job_from_form()
        if not row or not row["job"]:
            return
        self.jobs.append(row)
        self.job_list.insert("end", str(row["job"]))

    def _update_job(self):
        sel = self.job_list.curselection()
        if not sel:
            return
        row = self._job_from_form()
        if not row or not row["job"]:
            return
        idx = sel[0]
        self.jobs[idx] = row
        self.job_list.delete(idx)
        self.job_list.insert(idx, str(row["job"]))

    def _delete_job(self):
        sel = self.job_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.job_list.delete(idx)
        self.jobs.pop(idx)

    def _save_jobs(self):
        save_job_defs(self.jobs)
        messagebox.showinfo("저장 완료", "직업 데이터를 저장했습니다.")

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
        save_sim_settings(out)
        messagebox.showinfo("저장 완료", "시뮬레이션 설정을 저장했습니다.")


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
