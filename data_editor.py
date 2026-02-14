#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

DATA_DIR = Path(__file__).parent / "data"

VALID_JOBS = ["모험가", "농부", "어부", "대장장이", "약사"]
VALID_GENDERS = ["남", "여", "기타"]
ENTITY_TYPES = ["workbench", "resource"]

TAB_SCHEMAS: dict[str, tuple[str, list[tuple[str, str, str, list[str] | None]]]] = {
    "items.json": ("아이템", [
        ("key", "아이템 키", "str", None),
        ("display", "표시 이름", "str", None),
        ("is_craftable", "제작 가능", "bool", None),
        ("is_gatherable", "채집 가능", "bool", None),
        ("craft_time", "제작 시간", "int", None),
        ("gather_time", "채집 시간", "int", None),
    ]),
    "npcs.json": ("NPC", [
        ("name", "이름", "str", None),
        ("race", "종족", "str", None),
        ("gender", "성별", "combo", VALID_GENDERS),
        ("age", "나이", "int", None),
        ("job", "직업", "combo", VALID_JOBS),
    ]),
    "monsters.json": ("몬스터", [
        ("name", "이름", "str", None),
        ("race", "종족", "str", None),
        ("gender", "성별", "combo", VALID_GENDERS),
        ("age", "나이", "int", None),
        ("job", "직업", "combo", VALID_JOBS),
    ]),
    "races.json": ("종족", [
        ("name", "종족명", "str", None),
        ("is_hostile", "적대 여부", "bool", None),
        ("str_bonus", "힘 보너스", "int", None),
        ("agi_bonus", "민첩 보너스", "int", None),
        ("hp_bonus", "체력 보너스", "int", None),
        ("speed_bonus", "속도 보너스(정수)", "int", None),
    ]),
    "entities.json": ("엔티티", [
        ("type", "유형", "combo", ENTITY_TYPES),
        ("name", "이름", "str", None),
        ("x", "X", "int", None),
        ("y", "Y", "int", None),
        ("stock", "재고", "int", None),
    ]),
    "jobs.json": ("직업", [
        ("job", "직업", "combo", VALID_JOBS),
        ("sell_limit", "판매 한도", "int", None),
        ("sell_items_csv", "판매 아이템(csv)", "str", None),
    ]),
}

DICT_TABS = [("sim_settings.json", "시뮬 설정"), ("combat.json", "전투 설정")]


class ListTab:
    def __init__(self, parent: ttk.Frame, filename: str, schema: list[tuple[str, str, str, list[str] | None]]):
        self.filename = filename
        self.path = DATA_DIR / filename
        self.schema = schema
        self.rows: list[dict[str, object]] = []
        self.widgets: dict[str, tk.Widget] = {}
        self.bool_vars: dict[str, tk.BooleanVar] = {}

        ttk.Label(parent, text=f"JSON 파일: {filename}").pack(anchor="w", padx=8, pady=(8, 0))

        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(parent)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        ttk.Label(left, text="항목 선택").pack(anchor="w", pady=(0, 4))
        self.pick_var = tk.StringVar()
        self.pick_box = ttk.Combobox(left, textvariable=self.pick_var, state="readonly", width=36)
        self.pick_box.pack(fill="x", pady=(0, 8))
        self.pick_box.bind("<<ComboboxSelected>>", self._on_select)

        ttk.Button(left, text="새 항목", command=self._new).pack(fill="x", pady=2)
        ttk.Button(left, text="추가", command=self._add).pack(fill="x", pady=2)
        ttk.Button(left, text="수정", command=self._update).pack(fill="x", pady=2)
        ttk.Button(left, text="삭제", command=self._delete).pack(fill="x", pady=2)
        ttk.Button(left, text="저장", command=self._save).pack(fill="x", pady=(10, 2))

        for idx, (key, label, kind, options) in enumerate(schema):
            ttk.Label(right, text=label).grid(row=idx, column=0, sticky="w", pady=3)
            if kind == "bool":
                var = tk.BooleanVar(value=False)
                w = ttk.Checkbutton(right, variable=var)
                self.bool_vars[key] = var
            elif kind == "combo":
                w = ttk.Combobox(right, values=options or [], state="readonly", width=40)
            else:
                w = ttk.Entry(right, width=43)
            w.grid(row=idx, column=1, sticky="w", pady=3)
            self.widgets[key] = w

        self._load()

    def _read_list(self) -> list[dict[str, object]]:
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []
        except Exception:
            return []

    def _write_list(self) -> None:
        self.path.write_text(json.dumps(self.rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _display_text(self, row: dict[str, object], idx: int) -> str:
        if "name" in row:
            return f"{idx}: {row.get('name', '')}"
        if "key" in row:
            return f"{idx}: {row.get('key', '')}"
        if "job" in row:
            return f"{idx}: {row.get('job', '')}"
        return f"{idx}: 항목"

    def _refresh_combo(self) -> None:
        labels = [self._display_text(r, i) for i, r in enumerate(self.rows)]
        self.pick_box["values"] = labels
        if labels:
            self.pick_box.current(0)
            self._fill_form(0)
        else:
            self.pick_var.set("")
            self._clear_form()

    def _clear_form(self) -> None:
        for key, _, kind, _ in self.schema:
            if kind == "bool":
                self.bool_vars[key].set(False)
            elif kind == "combo":
                cast = self.widgets[key]
                if isinstance(cast, ttk.Combobox):
                    cast.set("")
            else:
                cast = self.widgets[key]
                if isinstance(cast, ttk.Entry):
                    cast.delete(0, "end")

    def _fill_form(self, index: int) -> None:
        if not (0 <= index < len(self.rows)):
            return
        row = self.rows[index]
        for key, _, kind, _ in self.schema:
            value = row.get(key, "")
            if key == "sell_items_csv":
                value = ",".join([str(v) for v in row.get("sell_items", [])])
            if kind == "bool":
                self.bool_vars[key].set(bool(value))
            elif kind == "combo":
                cast = self.widgets[key]
                if isinstance(cast, ttk.Combobox):
                    cast.set(str(value))
            else:
                cast = self.widgets[key]
                if isinstance(cast, ttk.Entry):
                    cast.delete(0, "end")
                    cast.insert(0, str(value))

    def _row_from_form(self) -> dict[str, object] | None:
        out: dict[str, object] = {}
        try:
            for key, _, kind, _ in self.schema:
                if kind == "bool":
                    out[key] = bool(self.bool_vars[key].get())
                elif kind == "combo":
                    cast = self.widgets[key]
                    out[key] = cast.get().strip() if isinstance(cast, ttk.Combobox) else ""
                else:
                    cast = self.widgets[key]
                    text = cast.get().strip() if isinstance(cast, ttk.Entry) else ""
                    if kind == "int":
                        out[key] = int(text or "0")
                    else:
                        out[key] = text

            if "sell_items_csv" in out:
                csv = str(out.pop("sell_items_csv", ""))
                out["sell_items"] = [s.strip() for s in csv.split(",") if s.strip()]

            return out
        except ValueError:
            messagebox.showwarning("경고", "정수 필드는 숫자만 입력하세요.")
            return None

    def _selected_index(self) -> int | None:
        text = self.pick_var.get().strip()
        if not text:
            return None
        head = text.split(":", 1)[0].strip()
        try:
            return int(head)
        except ValueError:
            return None

    def _on_select(self, _event=None) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        self._fill_form(idx)

    def _new(self) -> None:
        self._clear_form()

    def _add(self) -> None:
        row = self._row_from_form()
        if row is None:
            return
        self.rows.append(row)
        self._refresh_combo()

    def _update(self) -> None:
        idx = self._selected_index()
        if idx is None or not (0 <= idx < len(self.rows)):
            return
        row = self._row_from_form()
        if row is None:
            return
        self.rows[idx] = row
        self._refresh_combo()
        self.pick_box.current(idx)

    def _delete(self) -> None:
        idx = self._selected_index()
        if idx is None or not (0 <= idx < len(self.rows)):
            return
        self.rows.pop(idx)
        self._refresh_combo()

    def _save(self) -> None:
        self._write_list()
        messagebox.showinfo("저장 완료", f"{self.filename} 저장 완료")

    def _load(self) -> None:
        self.rows = self._read_list()
        self._refresh_combo()


class DictTab:
    def __init__(self, parent: ttk.Frame, filename: str):
        self.filename = filename
        self.path = DATA_DIR / filename
        self.entries: dict[str, ttk.Entry] = {}
        self.row_count = 0

        ttk.Label(parent, text=f"JSON 파일: {filename}").pack(anchor="w", padx=12, pady=(8, 0))

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        self.inner = ttk.Frame(frame)
        self.inner.pack(fill="x")

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="키 추가", command=self._add_key_row).pack(side="left", padx=3)
        ttk.Button(btns, text="저장", command=self._save).pack(side="left", padx=3)

        self._load()

    def _add_key_row(self, key: str = "", value: int = 0) -> None:
        row = self.row_count
        key_entry = ttk.Entry(self.inner, width=26)
        val_entry = ttk.Entry(self.inner, width=26)
        key_entry.grid(row=row, column=0, sticky="w", pady=3)
        val_entry.grid(row=row, column=1, sticky="w", pady=3, padx=8)
        key_entry.insert(0, key)
        val_entry.insert(0, str(value))
        self.entries[f"k{row}"] = key_entry
        self.entries[f"v{row}"] = val_entry
        self.row_count += 1

    def _load(self) -> None:
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        for child in self.inner.winfo_children():
            child.destroy()
        self.entries.clear()
        self.row_count = 0
        for k, v in data.items():
            try:
                iv = int(v)
            except Exception:
                iv = 0
            self._add_key_row(str(k), iv)
        if not data:
            self._add_key_row()

    def _save(self) -> None:
        out: dict[str, int] = {}
        try:
            for i in range(self.row_count):
                k_entry = self.entries.get(f"k{i}")
                v_entry = self.entries.get(f"v{i}")
                if not isinstance(k_entry, ttk.Entry) or not isinstance(v_entry, ttk.Entry):
                    continue
                key = k_entry.get().strip()
                if not key:
                    continue
                out[key] = int(v_entry.get().strip() or "0")
        except ValueError:
            messagebox.showwarning("경고", "값은 정수만 입력하세요.")
            return

        self.path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("저장 완료", f"{self.filename} 저장 완료")


class EditorApp(tk.Tk):
    """data/*.json 파일을 탭 단위로 수정/추가/저장하는 도구."""

    def __init__(self) -> None:
        super().__init__()
        self.title("데이터 에디터")
        self.geometry("1100x760")
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        ttk.Label(self, text="JSON 파일은 상단 탭으로 선택합니다.").pack(anchor="w", padx=10, pady=(8, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_tabs()

    def _build_tabs(self) -> None:
        """탭 UI를 명시적으로 구성한다."""
        for filename, (tab_title, schema) in TAB_SCHEMAS.items():
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=tab_title)
            ListTab(tab, filename, schema)

        for filename, tab_title in DICT_TABS:
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=tab_title)
            DictTab(tab, filename)


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
