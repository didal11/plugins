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


def test_start_action_cast_sets_pending_and_tick():
    engine = combat_scene.build_default_engine(seed=1)
    actor = next(x for x in engine.actors if x.name == "에린")

    started = engine.start_action_cast(actor, "attack")

    assert started is True
    assert actor.pending_action == "attack"
    assert actor.cast_started_tick == engine.current_tick
    assert actor.next_action_tick == engine.current_tick + engine.action_defs["attack"].tick_cost


def test_resolve_cast_if_ready_executes_and_clears_pending():
    engine = combat_scene.build_default_engine(seed=1)
    actor = next(x for x in engine.actors if x.name == "에린")
    target = next(x for x in engine.actors if x.name == "슬라임A")
    target.x = actor.x + 1
    target.y = actor.y

    assert engine.start_action_cast(actor, "attack") is True
    engine.current_tick = actor.next_action_tick

    resolved = engine.resolve_cast_if_ready(actor)

    assert resolved is True
    assert actor.pending_action is None
    assert target.hp < 30
