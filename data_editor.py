#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


DATA_DIR = Path(__file__).parent / "data"
JSON_FILES = [
    "items.json",
    "npcs.json",
    "monsters.json",
    "races.json",
    "entities.json",
    "jobs.json",
    "sim_settings.json",
    "combat.json",
]


class EditorApp(tk.Tk):
    """JSON 데이터 파일 수정/추가/저장 전용 에디터.

    목적: 실행 전에 data/*.json 파일을 간편하게 바꾸는 것.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("데이터 파일 에디터")
        self.geometry("1100x760")

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="파일").pack(side="left")
        self.file_var = tk.StringVar(value=JSON_FILES[0])
        self.file_box = ttk.Combobox(top, textvariable=self.file_var, values=JSON_FILES, state="readonly", width=28)
        self.file_box.pack(side="left", padx=8)
        self.file_box.bind("<<ComboboxSelected>>", self._open_selected_file)

        ttk.Button(top, text="새 객체 추가", command=self._append_object).pack(side="left", padx=4)
        ttk.Button(top, text="저장", command=self._save_current_file).pack(side="left", padx=4)

        self.path_label = ttk.Label(self, text="")
        self.path_label.pack(fill="x", padx=10)

        self.editor = tk.Text(self, wrap="none", font=("Consolas", 11))
        self.editor.pack(fill="both", expand=True, padx=10, pady=(6, 10))

        self._open_selected_file()

    def _selected_path(self) -> Path:
        filename = self.file_var.get().strip()
        if not filename:
            filename = JSON_FILES[0]
        return DATA_DIR / filename

    def _open_selected_file(self, _event=None) -> None:
        path = self._selected_path()
        if not path.exists():
            default_data = {} if path.name.endswith("settings.json") or path.name == "combat.json" else []
            path.write_text(json.dumps(default_data, ensure_ascii=False, indent=2), encoding="utf-8")

        raw_text = path.read_text(encoding="utf-8")
        try:
            parsed = json.loads(raw_text) if raw_text.strip() else []
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            pretty = raw_text

        self.path_label.configure(text=f"경로: {path}")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", pretty)

    def _append_object(self) -> None:
        path = self._selected_path()
        current = self.editor.get("1.0", "end").strip()
        try:
            value = json.loads(current) if current else []
        except Exception:
            messagebox.showwarning("경고", "현재 JSON 형식이 올바르지 않습니다. 먼저 JSON 오류를 수정하세요.")
            return

        if isinstance(value, list):
            value.append({})
        elif isinstance(value, dict):
            value[f"new_key_{len(value) + 1}"] = ""
        else:
            messagebox.showwarning("경고", "루트는 객체({}) 또는 배열([])이어야 새 데이터를 추가할 수 있습니다.")
            return

        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", json.dumps(value, ensure_ascii=False, indent=2))
        self.path_label.configure(text=f"경로: {path}")

    def _save_current_file(self) -> None:
        path = self._selected_path()
        raw_text = self.editor.get("1.0", "end").strip()

        if not raw_text:
            messagebox.showwarning("경고", "빈 내용은 저장할 수 없습니다.")
            return

        try:
            parsed = json.loads(raw_text)
        except Exception as exc:
            messagebox.showerror("저장 실패", f"JSON 형식 오류: {exc}")
            return

        path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("저장 완료", f"{path.name} 파일을 저장했습니다.")


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
