#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""pygame bridge module.

- 실제 pygame 패키지가 있으면 그것을 우선 사용.
- 없으면 headless fallback 제공.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path


def _load_real_pygame():
    this_dir = Path(__file__).resolve().parent
    search_path = [p for p in sys.path if p and Path(p).resolve() != this_dir]
    spec = importlib.machinery.PathFinder.find_spec("pygame", search_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    prev = sys.modules.get("pygame")
    try:
        # pygame 패키지 내부의 `import pygame.base`를 위해 sys.modules 교체
        sys.modules["pygame"] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        if prev is not None:
            sys.modules["pygame"] = prev
        else:
            sys.modules.pop("pygame", None)
        return None


_REAL = _load_real_pygame()

if _REAL is not None:
    globals().update(_REAL.__dict__)
else:
    SRCALPHA = 0
    QUIT = 0
    MOUSEWHEEL = 1
    MOUSEBUTTONDOWN = 2
    KEYDOWN = 3

    K_ESCAPE = 27
    K_i = ord("i")
    K_1 = ord("1")
    K_2 = ord("2")
    K_3 = ord("3")
    K_a = ord("a")
    K_d = ord("d")
    K_w = ord("w")
    K_s = ord("s")
    K_LEFT = 1000
    K_RIGHT = 1001
    K_UP = 1002
    K_DOWN = 1003

    class Rect:
        def __init__(self, x: int, y: int, w: int, h: int):
            self.x = int(x)
            self.y = int(y)
            self.w = int(w)
            self.h = int(h)

        def __iter__(self):
            return iter((self.x, self.y, self.w, self.h))

        def copy(self) -> "Rect":
            return Rect(self.x, self.y, self.w, self.h)

        @property
        def centerx(self) -> int:
            return self.x + self.w // 2

        @property
        def centery(self) -> int:
            return self.y + self.h // 2

        def collidepoint(self, px: int, py: int) -> bool:
            return self.x <= int(px) < self.x + self.w and self.y <= int(py) < self.y + self.h

        def inflate(self, dx: int, dy: int) -> "Rect":
            dx = int(dx)
            dy = int(dy)
            return Rect(self.x - dx // 2, self.y - dy // 2, self.w + dx, self.h + dy)

        def union_ip(self, other: "Rect") -> None:
            x0 = min(self.x, other.x)
            y0 = min(self.y, other.y)
            x1 = max(self.x + self.w, other.x + other.w)
            y1 = max(self.y + self.h, other.y + other.h)
            self.x, self.y, self.w, self.h = x0, y0, x1 - x0, y1 - y0

        def clamp_ip(self, bounds: "Rect") -> None:
            x0 = max(self.x, bounds.x)
            y0 = max(self.y, bounds.y)
            x1 = min(self.x + self.w, bounds.x + bounds.w)
            y1 = min(self.y + self.h, bounds.y + bounds.h)
            if x1 < x0:
                x1 = x0
            if y1 < y0:
                y1 = y0
            self.x, self.y, self.w, self.h = x0, y0, x1 - x0, y1 - y0

    class font:
        class Font:
            pass

        @staticmethod
        def SysFont(*_args, **_kwargs):
            raise RuntimeError("pygame font is unavailable in this headless fallback")

    def init():
        raise RuntimeError("pygame display is unavailable in this headless fallback")
