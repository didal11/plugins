#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Minimal pygame compatibility layer for headless/text simulation.

This fallback implements only a tiny subset used by simulation core.
Rendering APIs are intentionally unavailable in this environment.
"""

from __future__ import annotations

SRCALPHA = 0
QUIT = 0
MOUSEWHEEL = 1
MOUSEBUTTONDOWN = 2
KEYDOWN = 3

K_ESCAPE = 27
K_i = ord('i')
K_1 = ord('1')
K_2 = ord('2')
K_3 = ord('3')
K_a = ord('a')
K_d = ord('d')
K_w = ord('w')
K_s = ord('s')
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
