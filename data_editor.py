#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Simple no-code data editor (items, NPC templates, combat settings)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from editable_data import (
    VALID_JOBS,
    load_combat_settings,
    load_item_defs,
    load_npc_templates,
    save_combat_settings,
    save_item_defs,
    save_npc_templates,
)


class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Village Data Editor")
        self.geometry("980x670")

        self.items = load_item_defs()
        self.npcs = load_npc_templates()
        self.combat = load_combat_settings()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.item_tab = ttk.Frame(nb)
        self.npc_tab = ttk.Frame(nb)
        self.combat_tab = ttk.Frame(nb)
        nb.add(self.item_tab, text="아이템")
        nb.add(self.npc_tab, text="NPC")
        nb.add(self.combat_tab, text="전투로직")

        self._build_item_tab()
        self._build_npc_tab()
        self._build_combat_tab()

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

        ttk.Label(right, text="키").grid(row=0, column=0, sticky="w", pady=4)
        self.item_key = ttk.Entry(right, width=40)
        self.item_key.grid(row=0, column=1, sticky="w")

        ttk.Label(right, text="표시명").grid(row=1, column=0, sticky="w", pady=4)
        self.item_disp = ttk.Entry(right, width=40)
        self.item_disp.grid(row=1, column=1, sticky="w")

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
        self.item_key.insert(0, it["key"])
        self.item_disp.delete(0, "end")
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
        key = self.item_key.get().strip()
        disp = self.item_disp.get().strip()
        if not key or not disp:
            return
        idx = sel[0]
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
            self.npc_list.insert("end", f"{n['name']} ({n['job']}/{n['race']})")

        fields = ["name", "race", "gender", "age", "height_cm", "weight_kg", "job", "goal", "max_hp", "hp", "strength", "agility"]
        labels = {
            "name": "이름",
            "race": "종족(적대 가능)",
            "gender": "성별",
            "age": "나이",
            "height_cm": "키(cm)",
            "weight_kg": "몸무게(kg)",
            "job": "직업",
            "goal": "목표",
            "max_hp": "최대 체력",
            "hp": "현재 체력",
            "strength": "힘",
            "agility": "민첩",
        }
        self.npc_entries = {}
        for i, f in enumerate(fields):
            ttk.Label(right, text=labels[f]).grid(row=i, column=0, sticky="w", pady=2)
            if f == "job":
                w = ttk.Combobox(right, values=VALID_JOBS, state="readonly", width=37)
            else:
                w = ttk.Entry(right, width=40)
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
            val = str(n.get(k, ""))
            if isinstance(w, ttk.Combobox):
                w.set(val)
            else:
                w.delete(0, "end")
                w.insert(0, val)

    def _npc_from_form(self):
        try:
            max_hp = int(self.npc_entries["max_hp"].get().strip() or "100")
            hp = int(self.npc_entries["hp"].get().strip() or str(max_hp))
            return {
                "name": self.npc_entries["name"].get().strip(),
                "race": self.npc_entries["race"].get().strip() or "인간",
                "gender": self.npc_entries["gender"].get().strip() or "기타",
                "age": int(self.npc_entries["age"].get().strip() or "25"),
                "height_cm": int(self.npc_entries["height_cm"].get().strip() or "170"),
                "weight_kg": int(self.npc_entries["weight_kg"].get().strip() or "65"),
                "job": self.npc_entries["job"].get().strip() or "농부",
                "goal": self.npc_entries["goal"].get().strip() or "돈벌기",
                "max_hp": max(1, max_hp),
                "hp": max(0, min(max(1, max_hp), hp)),
                "strength": max(1, int(self.npc_entries["strength"].get().strip() or "10")),
                "agility": max(1, int(self.npc_entries["agility"].get().strip() or "10")),
            }
        except ValueError:
            messagebox.showwarning("경고", "숫자 항목(나이/키/몸무게/체력/힘/민첩)을 확인하세요.")
            return None

    def _add_npc(self):
        npc = self._npc_from_form()
        if not npc or not npc["name"]:
            return
        self.npcs.append(npc)
        self.npc_list.insert("end", f"{npc['name']} ({npc['job']}/{npc['race']})")

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
        self.npc_list.insert(idx, f"{npc['name']} ({npc['job']}/{npc['race']})")

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

    def _build_combat_tab(self):
        fields = [
            ("hostile_race", "적대 종족명"),
            ("engage_range_tiles", "교전 거리(타일)"),
            ("base_hit_chance", "기본 명중률(0~1)"),
            ("agility_evasion_scale", "민첩 회피 계수"),
            ("min_damage", "최소 피해"),
            ("max_damage", "최대 피해"),
            ("strength_damage_scale", "힘 피해 계수"),
            ("adventurer_attack_bonus", "모험가 공격 보너스"),
            ("hostile_attack_bonus", "적대 공격 보너스"),
        ]
        self.combat_entries = {}
        for i, (key, label) in enumerate(fields):
            ttk.Label(self.combat_tab, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=6)
            e = ttk.Entry(self.combat_tab, width=40)
            e.grid(row=i, column=1, sticky="w", padx=8, pady=6)
            e.insert(0, str(self.combat.get(key, "")))
            self.combat_entries[key] = e

        ttk.Button(self.combat_tab, text="전투 설정 저장", command=self._save_combat).grid(row=len(fields), column=1, sticky="w", padx=8, pady=12)

    def _save_combat(self):
        try:
            payload = {
                "hostile_race": self.combat_entries["hostile_race"].get().strip() or "적대",
                "engage_range_tiles": int(self.combat_entries["engage_range_tiles"].get().strip() or "2"),
                "base_hit_chance": float(self.combat_entries["base_hit_chance"].get().strip() or "0.75"),
                "agility_evasion_scale": float(self.combat_entries["agility_evasion_scale"].get().strip() or "0.015"),
                "min_damage": int(self.combat_entries["min_damage"].get().strip() or "5"),
                "max_damage": int(self.combat_entries["max_damage"].get().strip() or "14"),
                "strength_damage_scale": float(self.combat_entries["strength_damage_scale"].get().strip() or "0.45"),
                "adventurer_attack_bonus": float(self.combat_entries["adventurer_attack_bonus"].get().strip() or "0.10"),
                "hostile_attack_bonus": float(self.combat_entries["hostile_attack_bonus"].get().strip() or "0.05"),
            }
        except ValueError:
            messagebox.showwarning("경고", "전투 설정 숫자 항목을 확인하세요.")
            return
        save_combat_settings(payload)
        self.combat = load_combat_settings()
        messagebox.showinfo("저장 완료", "전투 설정을 저장했습니다.")


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
