from __future__ import annotations

import sys
from types import SimpleNamespace

import combat_scene


def test_parse_args_arcade_only(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["combat_scene.py", "--seed", "7", "--tick-seconds", "0.2"])

    args = combat_scene.parse_args()

    assert args.seed == 7
    assert args.tick_seconds == 0.2
    assert not hasattr(args, "backend")
    assert not hasattr(args, "auto")
    assert not hasattr(args, "max_ticks")


def test_rect_points_returns_lrbt_order():
    rect = SimpleNamespace(left=1, right=2, bottom=3, top=4)

    assert combat_scene.CombatSceneArcadeWindow._rect_points(rect) == (1, 2, 3, 4)
